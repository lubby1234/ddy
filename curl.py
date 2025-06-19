import subprocess
import os

# --- Configuration ---
AUTH_URLS_FILE = "signatureURLs.txt" # The file containing the list of auth.php URLs

def execute_curl_commands_from_file(file_path):
    """
    Reads a file containing URLs and executes a curl -I command for each URL.
    """
    print(f"Reading URLs from '{file_path}' and executing curl commands...\n")
    
    try:
        with open(file_path, 'r') as f:
            urls = [line.strip() for line in f if line.strip()] # Read non-empty lines
        
        if not urls:
            print(f"No URLs found in '{file_path}'. Exiting.")
            return

        for url in urls:
            print(f"Executing curl for: {url}")
            
            # Construct the curl command as a list of strings
            # -I performs a HEAD request
            # -H adds custom headers
            curl_cmd = [
                "curl", "-I",
                "-H", "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:139.0) Gecko/20100101 Firefox/139.0",
                "-H", "origin: https://lefttoplay.xyz",
                "-H", "referer: https://lefttoplay.xyz/",
                url
            ]
            
            try:
                # Execute the curl command
                # capture_output=True captures stdout and stderr
                # text=True decodes stdout/stderr as text
                # check=False prevents it from raising an exception for non-zero exit codes (like 4xx/5xx HTTP errors)
                result = subprocess.run(curl_cmd, capture_output=True, text=True, check=False)
                
                # Check the return code
                if result.returncode == 0:
                    # Attempt to extract HTTP status from the output headers
                    status_line = result.stdout.splitlines()[0] if result.stdout else "No HTTP Status Line"
                    print(f"  SUCCESS. {status_line}")
                else:
                    print(f"  FAILED. Curl exited with code: {result.returncode}")
                    if result.stderr:
                        print(f"  Stderr: {result.stderr.strip()}")
                    if result.stdout:
                        print(f"  Stdout (headers): {result.stdout.strip()}")
                print("-" * 50) # Separator for clarity

            except FileNotFoundError:
                print(f"Error: 'curl' command not found. Please ensure curl is installed and in your system's PATH.")
                break # Exit if curl is not found
            except Exception as e:
                print(f"An unexpected error occurred while executing curl for '{url}': {e}")
                print("-" * 50)

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found. Please ensure it exists in the same directory as the script.")
    except Exception as e:
        print(f"An error occurred while reading '{file_path}': {e}")

# --- Main execution ---
if __name__ == "__main__":
    execute_curl_commands_from_file(AUTH_URLS_FILE)
    print("\nAll curl commands attempted.")
