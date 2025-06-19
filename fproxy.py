import socket
import threading
import select
import sys
import os

# --- Configuration ---
HOST = '0.0.0.0'  # Listen on all available interfaces
PORT = 8888       # Default proxy port
BUFFER_SIZE = 4096 # Buffer size for relaying data

# --- Helper Functions ---
def log_message(level, message):
    """Simple logging function."""
    print(f"[{level}] {message}")

def parse_http_request(data):
    """Parses the first line of an HTTP request to get the method, host, and port."""
    try:
        first_line = data.decode('latin-1').splitlines()[0]
        parts = first_line.split(' ')
        if len(parts) < 2:
            return None, None, None, None # Invalid request line

        method = parts[0]
        url = parts[1]

        if method == 'CONNECT': # HTTPS request
            # For CONNECT, URL is usually host:port
            host_port = url.split(':')
            host = host_port[0]
            port = int(host_port[1]) if len(host_port) > 1 else 443 # Default HTTPS port
            log_message("INFO", f"CONNECT request to {host}:{port}")
            return method, host, port, None
        else: # HTTP request
            # Try to find Host header for HTTP/1.1 requests
            host = None
            port = 80 # Default HTTP port

            # Parse URL for older HTTP versions or direct IP access
            if url.startswith('http://'):
                url_parts = url.split('/')
                host_path = url_parts[2]
                if ':' in host_path:
                    host, port_str = host_path.split(':')
                    port = int(port_str)
                else:
                    host = host_path
                # Reconstruct path for request to origin server
                path = '/' + '/'.join(url_parts[3:])
                return method, host, port, path
            else:
                # For HTTP/1.0 or when no scheme is in URL (e.g., GET /path HTTP/1.0)
                # We need to find the Host header in the full request
                headers = data.decode('latin-1').split('\r\n')
                for header in headers:
                    if header.lower().startswith('host:'):
                        host_header = header.split(':')[1].strip()
                        if ':' in host_header:
                            host, port_str = host_header.split(':')
                            port = int(port_str)
                        else:
                            host = host_header
                        break
                # If host is still None, it's a malformed request or direct IP
                if host is None:
                    # Fallback: assume the URL is just the path and hope it's an HTTP/1.0 request
                    # or an explicit full URL was given. This is less robust.
                    log_message("WARNING", f"Could not find Host header for HTTP request: {first_line}. Assuming direct URL or 1.0.")
                    return method, None, None, url # Cannot determine host/port reliably

                log_message("INFO", f"HTTP request to {host}:{port}{url}")
                return method, host, port, url # url here is the path, or full URL if scheme was present
    except Exception as e:
        log_message("ERROR", f"Error parsing HTTP request: {e} - Data: {data[:100]}")
        return None, None, None, None

def relay_data(source_socket, destination_socket):
    """Relays data between two sockets."""
    try:
        while True:
            # Use select to wait for data on either socket
            rlist, _, _ = select.select([source_socket, destination_socket], [], [], 1)
            if not rlist:
                # No data for 1 second, continue looping or break if idle for too long
                continue

            for sock in rlist:
                if sock == source_socket:
                    data = source_socket.recv(BUFFER_SIZE)
                    if not data:
                        return # Client disconnected
                    destination_socket.sendall(data)
                elif sock == destination_socket:
                    data = destination_socket.recv(BUFFER_SIZE)
                    if not data:
                        return # Destination disconnected
                    source_socket.sendall(data)
    except socket.error as e:
        log_message("WARNING", f"Socket error during data relay: {e}")
    except Exception as e:
        log_message("ERROR", f"Unexpected error during data relay: {e}")
    finally:
        # Ensure sockets are closed if relay loop exits
        try:
            source_socket.shutdown(socket.SHUT_RDWR)
            source_socket.close()
        except OSError:
            pass # Socket might already be closed
        try:
            destination_socket.shutdown(socket.SHUT_RDWR)
            destination_socket.close()
        except OSError:
            pass # Socket might already be closed

# --- Proxy Handler for each client ---
def handle_client(client_socket, client_address):
    """Handles a single client connection."""
    log_message("INFO", f"Handling connection from {client_address[0]}:{client_address[1]}")
    remote_socket = None
    try:
        # Receive the first chunk of data to determine request type
        first_data = client_socket.recv(BUFFER_SIZE)
        if not first_data:
            log_message("WARNING", "Client sent no initial data.")
            return

        method, host, port, path = parse_http_request(first_data)

        if not host or not port:
            log_message("ERROR", f"Could not determine destination for request from {client_address}: {first_data[:50]}...")
            client_socket.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return

        remote_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        remote_socket.settimeout(5) # Set a timeout for connecting to the remote server
        remote_socket.connect((host, port))
        log_message("INFO", f"Connected to destination {host}:{port}")

        if method == 'CONNECT':
            # For HTTPS, respond with 200 OK to the client
            client_socket.sendall(b"HTTP/1.1 200 Connection established\r\n\r\n")
            log_message("INFO", f"Sent 200 OK to {client_address} for CONNECT")
            # Now, simply relay data between client and remote server
            relay_data(client_socket, remote_socket)
        else:
            # For HTTP, forward the original request (potentially modified for Host header)
            # Reconstruct the request to ensure it's sent correctly to the origin server
            # For HTTP/1.1 proxies usually send only the path, but keep Host header
            # For this simple proxy, we'll strip the http://host:port from the URL if present
            # and send the modified request.
            modified_request = first_data
            if path and path.startswith('http://'):
                # Android TV might send full URLs even when proxy is used.
                # Remove the scheme and host:port part from the request line.
                first_line = modified_request.decode('latin-1').splitlines()[0]
                new_first_line = first_line.replace(f" {method} {path}", f" {method} {path.split('//')[1].split('/', 1)[-1]}")
                modified_request = new_first_line.encode('latin-1') + modified_request.decode('latin-1').split('\r\n', 1)[1].encode('latin-1')

            log_message("INFO", f"Forwarding HTTP request to {host}:{port}")
            remote_socket.sendall(modified_request)
            relay_data(client_socket, remote_socket)

    except socket.timeout:
        log_message("ERROR", f"Connection to {host}:{port} timed out from {client_address}")
        client_socket.sendall(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
    except ConnectionRefusedError:
        log_message("ERROR", f"Connection refused by {host}:{port} for {client_address}")
        client_socket.sendall(b"HTTP/1.1 502 Bad Gateway\r\n\r\n")
    except socket.gaierror:
        log_message("ERROR", f"Could not resolve host {host} for {client_address}")
        client_socket.sendall(b"HTTP/1.1 504 Gateway Timeout\r\n\r\n")
    except OSError as e:
        log_message("ERROR", f"OS Error during client handling for {client_address}: {e}")
    except Exception as e:
        log_message("ERROR", f"Unhandled error in handle_client for {client_address}: {e}")
    finally:
        log_message("INFO", f"Closing connection from {client_address}")
        if client_socket:
            try:
                client_socket.shutdown(socket.SHUT_RDWR)
                client_socket.close()
            except OSError:
                pass # Socket might already be closed
        if remote_socket:
            try:
                remote_socket.shutdown(socket.SHUT_RDWR)
                remote_socket.close()
            except OSError:
                pass # Socket might already be closed

# --- Main Proxy Server ---
def start_proxy_server(host, port):
    """Starts the main proxy server."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        log_message("INFO", f"Proxy server listening on {host}:{port}")
    except Exception as e:
        log_message("CRITICAL", f"Failed to start server: {e}")
        sys.exit(1)

    while True:
        try:
            client_socket, client_address = server_socket.accept()
            client_handler = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address)
            )
            client_handler.daemon = True # Allow main program to exit even if threads are running
            client_handler.start()
        except KeyboardInterrupt:
            log_message("INFO", "Proxy server shutting down...")
            break
        except Exception as e:
            log_message("ERROR", f"Error accepting new connection: {e}")

    server_socket.close()

if __name__ == "__main__":
    log_message("INFO", "Starting Python Forward Proxy")
    start_proxy_server(HOST, PORT)
