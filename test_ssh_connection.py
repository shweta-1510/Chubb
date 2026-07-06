"""
SSH Connection Diagnostic Script
Run this to test SSH connectivity to your server
"""
import paramiko
import socket
import sys
from pathlib import Path

def test_port_connectivity(host, port=22, timeout=5):
    """Test if port is reachable."""
    print(f"\n{'='*60}")
    print(f"1. Testing Port Connectivity: {host}:{port}")
    print(f"{'='*60}")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"✅ Port {port} is OPEN and reachable")
            return True
        else:
            print(f"❌ Port {port} is CLOSED or filtered (error code: {result})")
            print(f"\nThis means:")
            print(f"  • SSH service is not running on port {port}")
            print(f"  • Firewall is blocking the connection")
            print(f"  • Wrong IP address or port number")
            return False
    
    except socket.gaierror as e:
        print(f"❌ Cannot resolve hostname: {host}")
        print(f"Error: {e}")
        return False
    except socket.timeout:
        print(f"❌ Connection timeout to {host}:{port}")
        print(f"Server is not responding")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        return False


def test_ssh_connection(host, username, key_file=None, password=None, port=22):
    """Test SSH connection with key or password."""
    print(f"\n{'='*60}")
    print(f"2. Testing SSH Connection")
    print(f"{'='*60}")
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Username: {username}")
    
    if key_file:
        print(f"Auth Method: Key File ({Path(key_file).name})")
    else:
        print(f"Auth Method: Password")
    
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        connect_kwargs = {
            'hostname': host,
            'username': username,
            'port': port,
            'timeout': 30,
            'banner_timeout': 10,
            'auth_timeout': 30,
            'look_for_keys': False,
            'allow_agent': False
        }
        
        if key_file:
            key_path = Path(key_file)
            if not key_path.exists():
                print(f"❌ Key file not found: {key_file}")
                return False
            
            print(f"\nAttempting to load key file...")
            
            # Try different key types
            from paramiko import RSAKey, Ed25519Key, ECDSAKey, DSSKey
            
            key_obj = None
            for key_class in [RSAKey, Ed25519Key, ECDSAKey, DSSKey]:
                try:
                    key_obj = key_class.from_private_key_file(str(key_path))
                    print(f"✅ Successfully loaded {key_class.__name__} key")
                    break
                except Exception as e:
                    print(f"❌ Failed to load as {key_class.__name__}: {str(e)[:50]}")
            
            if not key_obj:
                print(f"\n⚠️  Could not load key file. Trying key_filename parameter...")
                connect_kwargs['key_filename'] = str(key_path)
            else:
                connect_kwargs['pkey'] = key_obj
        else:
            if not password:
                print(f"❌ No password provided")
                return False
            connect_kwargs['password'] = password
        
        print(f"\nConnecting to {host}...")
        ssh.connect(**connect_kwargs)
        
        print(f"✅ SSH connection successful!")
        
        # Test command execution
        print(f"\nTesting command execution...")
        stdin, stdout, stderr = ssh.exec_command('echo "Hello from SSH"')
        output = stdout.read().decode('utf-8').strip()
        
        if output == "Hello from SSH":
            print(f"✅ Command execution successful!")
        else:
            print(f"⚠️  Unexpected output: {output}")
        
        # Test systemctl command
        print(f"\nTesting systemctl command...")
        stdin, stdout, stderr = ssh.exec_command('systemctl --version')
        output = stdout.read().decode('utf-8')
        error = stderr.read().decode('utf-8')
        
        if output:
            print(f"✅ systemctl is available")
            print(f"Version: {output.split()[0] if output.split() else 'unknown'}")
        else:
            print(f"❌ systemctl not available or permission denied")
            if error:
                print(f"Error: {error[:100]}")
        
        ssh.close()
        print(f"\n✅ All SSH tests passed!")
        return True
    
    except paramiko.AuthenticationException as e:
        print(f"\n❌ Authentication Failed!")
        print(f"Error: {e}")
        print(f"\nPossible issues:")
        print(f"  • Wrong username")
        print(f"  • Wrong password/key file")
        print(f"  • Key not authorized on server")
        print(f"  • User doesn't have SSH access")
        return False
    
    except paramiko.SSHException as e:
        print(f"\n❌ SSH Error!")
        print(f"Error: {e}")
        print(f"\nPossible issues:")
        print(f"  • SSH service not running properly")
        print(f"  • Network/firewall blocking")
        print(f"  • SSH protocol mismatch")
        return False
    
    except socket.timeout:
        print(f"\n❌ Connection Timeout!")
        print(f"Server took too long to respond")
        return False
    
    except Exception as e:
        print(f"\n❌ Unexpected Error!")
        print(f"Error: {e}")
        return False


def main():
    """Main diagnostic function."""
    print("\n" + "="*60)
    print("SSH CONNECTION DIAGNOSTIC TOOL")
    print("="*60)
    
    # Get connection details
    print("\nEnter connection details:")
    host = input("Server IP/Hostname: ").strip()
    username = input("Username: ").strip()
    
    auth_method = input("Authentication (1=Key File, 2=Password): ").strip()
    
    key_file = None
    password = None
    
    if auth_method == "1":
        key_file = input("Path to key file: ").strip()
    else:
        import getpass
        password = getpass.getpass("Password: ")
    
    # Run tests
    port_ok = test_port_connectivity(host)
    
    if not port_ok:
        print("\n" + "="*60)
        print("⚠️  PORT NOT REACHABLE - Stopping here")
        print("="*60)
        print("\nBefore continuing, you need to:")
        print("1. Verify the IP address is correct")
        print("2. Ensure SSH service is running on the server")
        print("3. Check firewall rules (both server and network)")
        print("4. For AWS EC2: Check Security Group allows inbound SSH")
        print("5. For Azure: Check NSG rules allow SSH")
        print("\nTest manually:")
        print(f"  ssh {username}@{host}")
        print("\n" + "="*60)
        sys.exit(1)
    
    ssh_ok = test_ssh_connection(host, username, key_file, password)
    
    # Summary
    print("\n" + "="*60)
    print("DIAGNOSTIC SUMMARY")
    print("="*60)
    print(f"Port 22 Reachable: {'✅ Yes' if port_ok else '❌ No'}")
    print(f"SSH Connection:    {'✅ Success' if ssh_ok else '❌ Failed'}")
    print("="*60)
    
    if port_ok and ssh_ok:
        print("\n✅ All tests passed! Server is accessible.")
        print("You can now use this server in the Health Monitor application.")
    elif port_ok and not ssh_ok:
        print("\n⚠️  Port is reachable but SSH authentication failed.")
        print("Check your credentials (username, password, or key file).")
    else:
        print("\n❌ Cannot reach the server on port 22.")
        print("Fix network connectivity before testing SSH.")
    
    print("\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nTest cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
