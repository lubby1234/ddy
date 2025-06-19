import re
import os

def generate_auth_urls_from_channel_auth_file(file_path):
    """
    Reads channelAuth.txt, extracts authentication parameters for each channel,
    and generates a list of auth.php URLs.
    """
    auth_urls = []
    
    try:
        with open(file_path, 'r') as f:
            lines = f.readlines()

        i = 0
        while i < len(lines):
            line = lines[i].strip()
            
            channel_key = None
            auth_ts = None
            auth_rnd = None
            auth_sig = None

            # Look for channelKey
            key_match = re.search(r'var channelKey = "([^"]+)"', line)
            if key_match:
                channel_key = key_match.group(1)
                
                # Assume next 3 lines contain authTs, authRnd, authSig for this channelKey
                if i + 3 < len(lines):
                    ts_line = lines[i+1].strip()
                    rnd_line = lines[i+2].strip()
                    sig_line = lines[i+3].strip()

                    ts_match = re.search(r'var authTs\s*=\s*"([^"]+)"', ts_line)
                    rnd_match = re.search(r'var authRnd\s*=\s*"([^"]+)"', rnd_line)
                    sig_match = re.search(r'var authSig\s*=\s*"([^"]+)"', sig_line)

                    if ts_match and rnd_match and sig_match:
                        auth_ts = ts_match.group(1)
                        auth_rnd = rnd_match.group(1)
                        auth_sig = sig_match.group(1)

                        # Construct the URL using the extracted values
                        base_url = "https://top2new.newkso.ru/auth.php"
                        url = (f"{base_url}?channel_id={channel_key}"
                               f"&ts={auth_ts}"
                               f"&rnd={auth_rnd}"
                               f"&sig={auth_sig}")
                        auth_urls.append(url)
                        i += 4 # Move past these 4 lines and look for the next channelKey
                        continue # Continue to next iteration from the new position
                    else:
                        print(f"Warning: Incomplete auth data block found for channelKey '{channel_key}' (line {i+1}). Skipping this block.")
                        # If parsing fails for a block, just move to the next line and try again
                        i += 1 
                else:
                    print(f"Warning: Incomplete data block starting at line {i+1}. Not enough subsequent lines for authTs, authRnd, authSig. Skipping.")
                    i += 1 
            else:
                # If the current line is not a 'var channelKey' line, just move to the next line
                i += 1 

    except FileNotFoundError:
        print(f"Error: The file '{file_path}' was not found. Please ensure it exists in the same directory as the script.")
    except Exception as e:
        print(f"An unexpected error occurred while reading or parsing '{file_path}': {e}")
        
    return auth_urls

if __name__ == "__main__":
    channel_auth_file = "channelAuth.txt"
    output_urls_file = "signatureURLs.txt" # New output file name

    generated_urls = generate_auth_urls_from_channel_auth_file(channel_auth_file)
    
    if generated_urls:
        try:
            with open(output_urls_file, 'w') as f:
                for url in generated_urls:
                    f.write(url + '\n')
            print(f"Successfully generated {len(generated_urls)} auth.php URLs and saved them to '{output_urls_file}'.")
        except IOError as e:
            print(f"Error writing to file '{output_urls_file}': {e}")
    else:
        print(f"No auth.php URLs generated. Please check your '{channel_auth_file}' file's content and format.")