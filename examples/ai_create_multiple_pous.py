import subprocess
import sys

def create_pou(name, pou_type, language):
    """
    Calls the codesys-tools CLI to create a single POU.
    Returns True if successful, False otherwise.
    """
    command = [
        "codesys-tools", 
        "pou", "create", 
        "--name", name, 
        "--type", pou_type, 
        "--language", language
    ]
    
    print(f"Creating POU: {name} ({pou_type}, {language})...")
    
    try:
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"Successfully created: {name}")
            return True
        else:
            print(f"Failed to create: {name}")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"Error during POU creation: {e}")
        return False

def main():
    # Define the batch of POUs to be created
    pous_to_create = [
        {"name": "Motor_FB", "type": "FunctionBlock", "language": "ST"},
        {"name": "Sensor_PRG", "type": "Program", "language": "LD"},
        {"name": "Alarm_FUN", "type": "Function", "language": "ST"}
    ]
    
    success_count = 0
    total_count = len(pous_to_create)
    
    # Process each POU in the list
    for pou in pous_to_create:
        if create_pou(pou["name"], pou["type"], pou["language"]):
            success_count += 1
        else:
            # Decide if we should continue or stop on first failure
            print(f"Stopping execution due to failure in {pou['name']}.")
            sys.exit(1)
            
    print(f"\nBatch operation completed. {success_count}/{total_count} POUs created.")

if __name__ == "__main__":
    main()
