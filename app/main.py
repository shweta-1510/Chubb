"""
Main Streamlit application for Environment Health Check Monitor.
"""
import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List
import json
import os
from pathlib import Path

from app.database.db import init_db, get_db_context
from app.models.server import ServerModel
from app.models.monitored_service import MonitoredServiceModel
from app.services.health_check_service import HealthCheckService
from app.reports.html_report import HTMLReportGenerator
from app.reports.csv_report import CSVReportGenerator
from app.reports.xlsx_report import XLSXReportGenerator
from app.utils.logger import get_logger
from app.utils.bulk_import import BulkImportService
from app.utils.service_discovery import ServiceDiscovery
from app.config import config

# Initialize logger
logger = get_logger(__name__)

# Create credentials directory if it doesn't exist
CREDENTIALS_DIR = Path("credentials")
CREDENTIALS_DIR.mkdir(exist_ok=True)

# Page configuration
st.set_page_config(
    page_title="Environment Health Check Monitor",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize database
try:
    init_db()
except Exception as e:
    st.error(f"Failed to initialize database: {e}")
    st.stop()

# Initialize services
health_check_service = HealthCheckService()


def main():
    """Main application entry point."""
    st.title("🏥 Environment Health Check Monitor")
    st.markdown("---")
    
    # Sidebar navigation
    page = st.sidebar.selectbox(
        "Navigation",
        ["Server Registration", "Bulk Import Servers", "Health Check Execution", "View Servers", "Reports"]
    )
    
    if page == "Server Registration":
        show_server_registration()
    elif page == "Bulk Import Servers":
        show_bulk_import()
    elif page == "Health Check Execution":
        show_health_check_execution()
    elif page == "View Servers":
        show_servers_list()
    elif page == "Reports":
        show_reports()


def show_server_registration():
    """Display server registration form with new workflow."""
    st.header("📝 Server Registration")
    
    # Initialize session state for workflow
    if 'server_saved' not in st.session_state:
        st.session_state.server_saved = False
    if 'saved_server_id' not in st.session_state:
        st.session_state.saved_server_id = None
    if 'discovered_services' not in st.session_state:
        st.session_state.discovered_services = []
    if 'credential_file_path' not in st.session_state:
        st.session_state.credential_file_path = None
    
    # Step 1: Server Details Form
    st.subheader("Step 1: Server Details")
    
    # File uploader OUTSIDE the form (prevents React errors)
    st.markdown("**Credential Configuration**")
    uploaded_ppk = st.file_uploader(
        "Credential Reference (PPK/PEM File) *",
        type=['ppk', 'pem', 'key'],
        help="Upload private key file (PPK, PEM, or KEY format)",
        key="credential_uploader"
    )
    
    # Save uploaded file to session state
    if uploaded_ppk:
        # Save the uploaded file
        ppk_filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uploaded_ppk.name}"
        ppk_path = CREDENTIALS_DIR / ppk_filename
        
        with open(ppk_path, "wb") as f:
            f.write(uploaded_ppk.getbuffer())
        
        st.session_state.credential_file_path = str(ppk_path)
        st.success(f"✅ File uploaded: {ppk_filename}")
    
    st.markdown("---")
    
    with st.form("server_details_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            server_name = st.text_input("Server Name *", help="Unique server identifier")
            ip_address = st.text_input("IP Address *", help="Server IP address")
            hostname = st.text_input("Hostname", help="Server hostname (optional)")
            os_type = st.selectbox("OS Type *", ["Linux", "Windows"])
            environment = st.selectbox(
                "Environment",
                ["Development", "Staging", "UAT", "Production", "DR"]
            )
            cloud_provider = st.selectbox(
                "Cloud Provider",
                ["AWS", "Azure", "GCP", "On-Premise", "Other"]
            )
        
        with col2:
            connection_type = st.selectbox("Connection Type *", ["SSH", "WinRM"])
            username = st.text_input("Username *", help="Connection username")
            
            # Show credential file status
            if st.session_state.credential_file_path:
                st.info(f"📁 Credential file ready: {Path(st.session_state.credential_file_path).name}")
            else:
                st.warning("⚠️ Please upload a credential file above")
            
            # Database configuration
            st.markdown("**Database Configuration (Optional)**")
            database_type = st.selectbox(
                "Database Type",
                ["None", "PostgreSQL", "MySQL", "MSSQL"]
            )
            database_host = st.text_input("Database Host")
            database_port = st.number_input("Database Port", min_value=1, max_value=65535, value=5432)
        
        # Active status
        is_active = st.checkbox("Active", value=True, help="Enable health checks for this server")
        
        st.markdown("---")
        
        # Save Server Details Button
        save_button = st.form_submit_button("💾 Save Server Details", use_container_width=True, type="primary")
    
    # Handle Save Server Details
    if save_button:
        # Validate required fields
        if not server_name or not ip_address or not username:
            st.error("❌ Please fill in all required fields marked with *")
            return
        
        # Get credential file path from session state
        credential_reference = st.session_state.credential_file_path
        
        if not credential_reference:
            st.error("⚠️ Please upload a credential file (PPK/PEM/KEY)")
            return
        
        try:
            with get_db_context() as db:
                # Check if server already exists
                existing_server = db.query(ServerModel).filter(
                    ServerModel.server_name == server_name
                ).first()
                
                if existing_server:
                    st.error(f"❌ Server '{server_name}' already exists. Please use a unique name.")
                    return
                
                # Create server model
                server = ServerModel(
                    server_name=server_name,
                    ip_address=ip_address,
                    hostname=hostname if hostname else None,
                    os_type=os_type,
                    environment=environment,
                    cloud_provider=cloud_provider,
                    connection_type=connection_type,
                    username=username,
                    credential_reference=credential_reference,
                    database_type=database_type if database_type != "None" else None,
                    database_host=database_host if database_host else None,
                    database_port=database_port if database_host else None,
                    is_active=is_active
                )
                
                # Save to database
                db.add(server)
                db.commit()
                db.refresh(server)
                
                # Update session state
                st.session_state.server_saved = True
                st.session_state.saved_server_id = server.server_id
                
                st.success(f"✅ Server '{server_name}' details saved successfully!")
                logger.info(f"Server registered: {server_name} (ID: {server.server_id})")
                
        except Exception as e:
            st.error(f"❌ Error saving server: {e}")
            logger.error(f"Error saving server: {e}")
            return
    
    # Step 2: Service Discovery (only if server is saved)
    if st.session_state.server_saved and st.session_state.saved_server_id:
        st.markdown("---")
        st.subheader("Step 2: Service Discovery")
        
        # Fetch saved server details
        try:
            with get_db_context() as db:
                server = db.query(ServerModel).filter(
                    ServerModel.server_id == st.session_state.saved_server_id
                ).first()
                
                if not server:
                    st.error("❌ Saved server not found. Please save server details again.")
                    st.session_state.server_saved = False
                    st.session_state.saved_server_id = None
                    return
                
                st.info(f"📡 Server: **{server.server_name}** ({server.ip_address})")
                
                col1, col2 = st.columns([1, 3])
                
                with col1:
                    search_services_button = st.button(
                        "🔍 Search Available Services",
                        use_container_width=True,
                        type="primary"
                    )
                
                # Handle Service Discovery
                if search_services_button:
                    with st.spinner(f"Connecting to {server.server_name} and discovering services..."):
                        service_discovery = ServiceDiscovery()
                        success, services, error_msg = service_discovery.discover_services(server)
                        
                        if success:
                            st.session_state.discovered_services = services
                            st.success(f"✅ Discovered {len(services)} services on {server.server_name}")
                            logger.info(f"Discovered {len(services)} services on {server.server_name}")
                        else:
                            st.error(f"❌ Service discovery failed: {error_msg}")
                            logger.error(f"Service discovery failed for {server.server_name}: {error_msg}")
                            st.session_state.discovered_services = []
                
                # Step 3: Service Selection (only if services are discovered)
                if st.session_state.discovered_services:
                    st.markdown("---")
                    st.subheader("Step 3: Select Services to Monitor")
                    
                    # Get currently monitored services
                    current_services = db.query(MonitoredServiceModel).filter(
                        MonitoredServiceModel.server_id == server.server_id
                    ).all()
                    current_service_names = [s.service_name for s in current_services]
                    
                    st.info(f"📋 Found {len(st.session_state.discovered_services)} available services")
                    
                    # Multi-select dropdown with discovered services
                    selected_services = st.multiselect(
                        "Services to Monitor",
                        options=st.session_state.discovered_services,
                        default=current_service_names,
                        help="Select services to monitor for health checks"
                    )
                    
                    col1, col2, col3 = st.columns([1, 1, 3])
                    
                    with col1:
                        save_services_button = st.button(
                            "💾 Save Selected Services",
                            use_container_width=True,
                            type="primary"
                        )
                    
                    with col2:
                        finish_button = st.button(
                            "✅ Finish Registration",
                            use_container_width=True
                        )
                    
                    # Handle Save Selected Services
                    if save_services_button:
                        try:
                            # Delete existing monitored services
                            db.query(MonitoredServiceModel).filter(
                                MonitoredServiceModel.server_id == server.server_id
                            ).delete()
                            
                            # Add new monitored services
                            for service_name in selected_services:
                                monitored_service = MonitoredServiceModel(
                                    server_id=server.server_id,
                                    service_name=service_name
                                )
                                db.add(monitored_service)
                            
                            db.commit()
                            
                            st.success(f"✅ Saved {len(selected_services)} services for monitoring")
                            logger.info(f"Saved {len(selected_services)} monitored services for {server.server_name}")
                        
                        except Exception as e:
                            st.error(f"❌ Error saving services: {e}")
                            logger.error(f"Error saving monitored services: {e}")
                    
                    # Handle Finish Registration
                    if finish_button:
                        st.session_state.server_saved = False
                        st.session_state.saved_server_id = None
                        st.session_state.discovered_services = []
                        st.success("✅ Server registration completed successfully!")
                        st.info("You can now run health checks from the 'Health Check Execution' page")
                        st.balloons()
                
        except Exception as e:
            st.error(f"❌ Error: {e}")
            logger.error(f"Error in service discovery section: {e}")


def show_bulk_import():
    """Display bulk import interface for importing servers from CSV, XLSX, or YAML files."""
    st.header("📤 Bulk Import Servers")
    st.markdown("""
    Import multiple servers at once from CSV, Excel (XLSX), or YAML files. 
    You can also download templates to see the expected format.
    """)
    
    # Initialize bulk import service
    bulk_import_service = BulkImportService()
    
    # Create tabs for import and template download
    tab1, tab2 = st.tabs(["📥 Import Servers", "📄 Download Templates"])
    
    with tab1:
        st.subheader("Upload Server Data File")
        
        # File uploader
        uploaded_file = st.file_uploader(
            "Choose a file",
            type=['csv', 'xlsx', 'yaml', 'yml'],
            help="Upload a CSV, XLSX, or YAML file containing server data"
        )
        
        if uploaded_file:
            # Determine file type
            file_extension = uploaded_file.name.split('.')[-1].lower()
            if file_extension == 'yml':
                file_extension = 'yaml'
            
            st.info(f"📁 File: **{uploaded_file.name}** ({file_extension.upper()} format)")
            
            # Preview option
            show_preview = st.checkbox("Show file preview", value=True)
            
            if show_preview:
                try:
                    file_content = uploaded_file.getvalue()
                    
                    if file_extension in ['csv', 'xlsx']:
                        # Show as DataFrame
                        if file_extension == 'csv':
                            df = pd.read_csv(uploaded_file)
                        else:
                            df = pd.read_excel(uploaded_file, engine='openpyxl')
                        
                        st.dataframe(df, use_container_width=True)
                        st.caption(f"Preview: {len(df)} rows")
                    
                    elif file_extension == 'yaml':
                        # Show as text
                        yaml_text = file_content.decode('utf-8')
                        st.code(yaml_text, language='yaml')
                    
                    # Reset file pointer
                    uploaded_file.seek(0)
                
                except Exception as e:
                    st.warning(f"Could not preview file: {e}")
            
            st.markdown("---")
            
            # Import button
            col1, col2, col3 = st.columns([1, 2, 1])
            
            with col2:
                import_button = st.button(
                    "🚀 Import Servers",
                    use_container_width=True,
                    type="primary"
                )
            
            if import_button:
                try:
                    # Read file content
                    file_content = uploaded_file.getvalue()
                    
                    with st.spinner("Processing import file..."):
                        # Process the file
                        valid_servers, errors = bulk_import_service.process_import_file(
                            file_content,
                            file_extension
                        )
                    
                    # Display results
                    st.markdown("---")
                    st.subheader("📊 Import Results")
                    
                    # Summary metrics
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        st.metric("Total Entries", len(valid_servers) + len(errors))
                    
                    with col2:
                        st.metric("✅ Valid", len(valid_servers), delta_color="normal")
                    
                    with col3:
                        st.metric("❌ Errors", len(errors), delta_color="inverse")
                    
                    # Show errors if any
                    if errors:
                        st.error(f"⚠️ Found {len(errors)} invalid entries:")
                        error_df = pd.DataFrame(errors)
                        st.dataframe(error_df, use_container_width=True)
                    
                    # Import valid servers
                    if valid_servers:
                        st.success(f"✅ Found {len(valid_servers)} valid server(s) to import")
                        
                        # Confirm import
                        if st.button("Confirm Import to Database", type="primary"):
                            with st.spinner("Importing servers to database..."):
                                imported_count = 0
                                failed_imports = []
                                
                                with get_db_context() as db:
                                    for server_data in valid_servers:
                                        try:
                                            # Check if server already exists
                                            existing_server = db.query(ServerModel).filter(
                                                ServerModel.server_name == server_data['server_name']
                                            ).first()
                                            
                                            if existing_server:
                                                failed_imports.append({
                                                    'server_name': server_data['server_name'],
                                                    'reason': 'Server name already exists'
                                                })
                                                continue
                                            
                                            # Create new server
                                            server = ServerModel(**server_data)
                                            db.add(server)
                                            imported_count += 1
                                        
                                        except Exception as e:
                                            failed_imports.append({
                                                'server_name': server_data.get('server_name', 'Unknown'),
                                                'reason': str(e)
                                            })
                                    
                                    db.commit()
                            
                            # Show import results
                            st.markdown("---")
                            st.subheader("✅ Import Complete")
                            
                            col1, col2 = st.columns(2)
                            
                            with col1:
                                st.metric("Successfully Imported", imported_count)
                            
                            with col2:
                                st.metric("Failed", len(failed_imports))
                            
                            if failed_imports:
                                st.warning("Some servers failed to import:")
                                failed_df = pd.DataFrame(failed_imports)
                                st.dataframe(failed_df, use_container_width=True)
                            
                            logger.info(f"Bulk import completed: {imported_count} servers imported")
                    
                    else:
                        st.warning("No valid servers found to import.")
                
                except Exception as e:
                    st.error(f"❌ Error processing import file: {e}")
                    logger.error(f"Bulk import error: {e}")
        
        else:
            st.info("👆 Upload a file to begin the import process")
    
    with tab2:
        st.subheader("Download Import Templates")
        st.markdown("""
        Download a template file to see the expected format and required fields.
        Fill in your server information and upload it using the Import tab.
        """)
        
        # Required fields information
        with st.expander("📋 Required Fields", expanded=True):
            st.markdown("""
            **Required fields:**
            - `server_name` - Unique server identifier
            - `ip_address` - Server IP address
            - `os_type` - Operating system (Linux or Windows)
            - `connection_type` - Connection method (SSH or WinRM)
            - `username` - Username for connection
            
            **Optional fields:**
            - `hostname` - Server hostname
            - `environment` - Environment type (Development, Staging, UAT, Production, DR)
            - `cloud_provider` - Cloud provider (AWS, Azure, GCP, On-Premise, Other)
            - `credential_reference` - Password or path to credential file (e.g., credentials/key.ppk)
            - `services_to_monitor` - Comma-separated list of services
            - `database_type` - Database type (PostgreSQL, MySQL, MSSQL, or None)
            - `database_host` - Database host address
            - `database_port` - Database port number
            - `is_active` - Active status (True or False)
            """)
        
        # Download buttons
        col1, col2, col3 = st.columns(3)
        
        with col1:
            csv_template = bulk_import_service.generate_template_csv()
            st.download_button(
                label="📥 Download CSV Template",
                data=csv_template,
                file_name="server_import_template.csv",
                mime="text/csv",
                use_container_width=True
            )
        
        with col2:
            # Generate XLSX template
            import io
            xlsx_buffer = io.BytesIO()
            df = pd.read_csv(io.StringIO(csv_template))
            with pd.ExcelWriter(xlsx_buffer, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Servers')
            
            st.download_button(
                label="📥 Download XLSX Template",
                data=xlsx_buffer.getvalue(),
                file_name="server_import_template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
        
        with col3:
            yaml_template = bulk_import_service.generate_template_yaml()
            st.download_button(
                label="📥 Download YAML Template",
                data=yaml_template,
                file_name="server_import_template.yaml",
                mime="text/yaml",
                use_container_width=True
            )


def show_health_check_execution():
    """Display health check execution interface."""
    st.header("🔍 Health Check Execution")
    
    try:
        with get_db_context() as db:
            # Fetch active servers
            servers = db.query(ServerModel).filter(ServerModel.is_active == True).all()
            
            if not servers:
                st.warning("No active servers found. Please register servers first.")
                return
            
            # Server selection
            server_options = {f"{s.server_name} ({s.ip_address})": s for s in servers}
            
            selected_server_names = st.multiselect(
                "Select Servers to Check",
                options=list(server_options.keys()),
                help="Select one or more servers to run health checks"
            )
            
            # Show Run button immediately when server(s) selected
            if selected_server_names:
                st.markdown("---")
                
                # Execution button
                if st.button("▶️ Run Health Check", use_container_width=True, type="primary"):
                    selected_servers = [server_options[name] for name in selected_server_names]
                    
                    # Execute health checks with progress bar
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    results = []
                    for idx, server in enumerate(selected_servers):
                        status_text.text(f"Checking {server.server_name}...")
                        result = health_check_service.execute_health_check(server)
                        results.append(result)
                        progress_bar.progress((idx + 1) / len(selected_servers))
                    
                    status_text.text("✅ Health check completed!")
                    
                    # Store results in session state
                    st.session_state['health_check_results'] = results
                    
                    # Display results
                    display_health_check_results(results)
            
            # Show previous results if available
            elif 'health_check_results' in st.session_state and st.session_state['health_check_results']:
                st.info("📋 Showing previous health check results")
                display_health_check_results(st.session_state['health_check_results'])
                
    except Exception as e:
        st.error(f"Error: {e}")
        logger.error(f"Error in health check execution: {e}")


def display_health_check_results(results: List):
    """Display health check results with color-coded badges."""
    st.markdown("---")
    st.subheader("📊 Health Check Results")
    
    # Helper function for status badge
    def status_badge(status_value: str) -> str:
        """Generate HTML badge for status."""
        status_lower = status_value.lower()
        if status_lower in ['healthy', 'active', 'running']:
            return f'<span style="background-color: #28a745; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold;">✓ {status_value}</span>'
        elif status_lower in ['critical', 'inactive', 'stopped', 'failed']:
            return f'<span style="background-color: #dc3545; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold;">✗ {status_value}</span>'
        elif status_lower == 'warning':
            return f'<span style="background-color: #ffc107; color: black; padding: 4px 12px; border-radius: 12px; font-weight: bold;">⚠ {status_value}</span>'
        else:
            return f'<span style="background-color: #6c757d; color: white; padding: 4px 12px; border-radius: 12px; font-weight: bold;">{status_value}</span>'
    
    # Summary metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Servers", len(results))
    
    with col2:
        healthy_count = sum(1 for r in results if r.overall_status.value == "Healthy")
        st.metric("✅ Healthy", healthy_count)
    
    with col3:
        warning_count = sum(1 for r in results if r.overall_status.value == "Warning")
        st.metric("⚠️ Warning", warning_count)
    
    with col4:
        critical_count = sum(1 for r in results if r.overall_status.value in ["Critical", "Failed"])
        st.metric("❌ Critical", critical_count)
    
    # Detailed results for each server
    st.markdown("### Detailed Results")
    
    for result in results:
        # Server header with status badge
        status_color = "🟢" if result.overall_status.value == "Healthy" else "🔴" if result.overall_status.value in ["Critical", "Failed"] else "🟡"
        
        with st.expander(f"{status_color} {result.server_name} - {result.overall_status.value}", expanded=True):
            # Server and Execution Info
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**Server:** {result.server_name}")
            
            with col2:
                st.markdown(f"**Execution Time:** {result.execution_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            st.markdown("---")
            
            # Resource Health Section
            st.markdown("### 📊 Resource Health")
            
            # Create table-like display for resources
            if result.cpu_metric:
                cpu_status = "Healthy" if result.cpu_metric.status.value == "Healthy" else "Critical"
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown("**CPU Usage**")
                with col2:
                    st.markdown(f"{result.cpu_metric.usage:.2f}%")
                with col3:
                    st.markdown(status_badge(cpu_status), unsafe_allow_html=True)
            
            if result.memory_metric:
                memory_status = "Healthy" if result.memory_metric.status.value == "Healthy" else "Critical"
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown("**Memory Usage**")
                with col2:
                    st.markdown(f"{result.memory_metric.usage:.2f}%")
                with col3:
                    st.markdown(status_badge(memory_status), unsafe_allow_html=True)
            
            if result.disk_metric:
                disk_status = "Healthy" if result.disk_metric.status.value == "Healthy" else "Critical"
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown("**Disk Usage**")
                with col2:
                    st.markdown(f"{result.disk_metric.usage:.2f}%")
                with col3:
                    st.markdown(status_badge(disk_status), unsafe_allow_html=True)
            
            # Services Section
            if result.service_statuses:
                st.markdown("---")
                st.markdown("### 🔧 Services")
                
                for svc in result.service_statuses:
                    service_status_text = "Running" if svc.is_running else "Stopped"
                    health_status = "Healthy" if svc.is_running else "Critical"
                    
                    col1, col2, col3 = st.columns([2, 2, 1])
                    with col1:
                        st.markdown(f"**{svc.service_name}**")
                    with col2:
                        st.markdown(service_status_text)
                    with col3:
                        st.markdown(status_badge(health_status), unsafe_allow_html=True)
            
            # Database Section
            if result.database_status:
                st.markdown("---")
                st.markdown("### 💾 Database")
                
                db_status = "Connected" if result.database_status.is_connected else "Disconnected"
                db_health = "Healthy" if result.database_status.is_connected else "Critical"
                
                col1, col2, col3 = st.columns([2, 2, 1])
                with col1:
                    st.markdown(f"**{result.database_status.database_type}**")
                with col2:
                    st.markdown(f"{result.database_status.host}:{result.database_status.port} - {db_status}")
                with col3:
                    st.markdown(status_badge(db_health), unsafe_allow_html=True)
            
            # Overall Status
            st.markdown("---")
            col1, col2 = st.columns([3, 1])
            with col1:
                st.markdown("### **Overall Status**")
            with col2:
                st.markdown(f"## {status_badge(result.overall_status.value)}", unsafe_allow_html=True)
            
            # Error message
            if result.error_message:
                st.error(f"**Error:** {result.error_message}")


def show_servers_list():
    """Display list of registered servers."""
    st.header("📋 Registered Servers")
    
    try:
        with get_db_context() as db:
            servers = db.query(ServerModel).all()
            
            if not servers:
                st.info("No servers registered yet.")
                return
            
            # Convert to DataFrame
            server_data = []
            for server in servers:
                server_data.append({
                    "ID": server.server_id,
                    "Server Name": server.server_name,
                    "IP Address": server.ip_address,
                    "OS Type": server.os_type,
                    "Environment": server.environment or "N/A",
                    "Connection": server.connection_type,
                    "Active": "✅" if server.is_active else "❌",
                    "Services": len(server.services_to_monitor) if server.services_to_monitor else 0,
                    "Created": server.created_at.strftime('%Y-%m-%d') if server.created_at else "N/A"
                })
            
            df = pd.DataFrame(server_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
            
            # Server details
            st.markdown("---")
            st.subheader("Server Details")
            
            server_names = [s.server_name for s in servers]
            selected_server_name = st.selectbox("Select Server", server_names)
            
            if selected_server_name:
                server = next(s for s in servers if s.server_name == selected_server_name)
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("**Configuration**")
                    st.json(server.to_dict())
                
                with col2:
                    st.markdown("**Actions**")
                    
                    if st.button("🗑️ Delete Server", use_container_width=True):
                        try:
                            db.delete(server)
                            db.commit()
                            st.success(f"Server '{server.server_name}' deleted successfully!")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting server: {e}")
                    
                    if server.is_active:
                        if st.button("⏸️ Deactivate Server", use_container_width=True):
                            server.is_active = False
                            db.commit()
                            st.success("Server deactivated")
                            st.rerun()
                    else:
                        if st.button("▶️ Activate Server", use_container_width=True):
                            server.is_active = True
                            db.commit()
                            st.success("Server activated")
                            st.rerun()
            
    except Exception as e:
        st.error(f"Error: {e}")
        logger.error(f"Error displaying servers: {e}")


def show_reports():
    """Display report generation interface."""
    st.header("📄 Reports")
    
    if 'health_check_results' not in st.session_state or not st.session_state['health_check_results']:
        st.warning("No health check results available. Please run a health check first.")
        return
    
    results = st.session_state['health_check_results']
    
    st.info(f"Report contains results for {len(results)} server(s)")
    
    # Report format selection
    col1, col2, col3 = st.columns(3)
    
    try:
        # HTML Report
        with col1:
            st.subheader("HTML Report")
            if st.button("📄 Generate HTML", use_container_width=True):
                html_generator = HTMLReportGenerator()
                html_content = html_generator.generate(results)
                
                st.download_button(
                    label="⬇️ Download HTML",
                    data=html_content,
                    file_name=f"health_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    use_container_width=True
                )
        
        # CSV Report
        with col2:
            st.subheader("CSV Report")
            if st.button("📊 Generate CSV", use_container_width=True):
                csv_generator = CSVReportGenerator()
                csv_content = csv_generator.generate(results)
                
                st.download_button(
                    label="⬇️ Download CSV",
                    data=csv_content,
                    file_name=f"health_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
        
        # XLSX Report
        with col3:
            st.subheader("Excel Report")
            if st.button("📈 Generate XLSX", use_container_width=True):
                import tempfile
                
                xlsx_generator = XLSXReportGenerator()
                
                with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsx') as tmp_file:
                    xlsx_generator.generate(results, tmp_file.name)
                    
                    with open(tmp_file.name, 'rb') as file:
                        xlsx_content = file.read()
                    
                    st.download_button(
                        label="⬇️ Download XLSX",
                        data=xlsx_content,
                        file_name=f"health_check_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
    
    except Exception as e:
        st.error(f"Error generating report: {e}")
        logger.error(f"Error generating report: {e}")


if __name__ == "__main__":
    main()
