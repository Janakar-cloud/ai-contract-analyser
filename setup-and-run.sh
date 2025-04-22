#!/bin/bash

# Contract Anomaly Detection System Setup Script
# This script helps set up and run the Contract Anomaly Detection system on your local WSL Ubuntu machine

# Function to display colored messages
print_message() {
  local color=$1
  local message=$2
  case $color in
    "green") echo -e "\e[32m$message\e[0m" ;;
    "red") echo -e "\e[31m$message\e[0m" ;;
    "yellow") echo -e "\e[33m$message\e[0m" ;;
    "blue") echo -e "\e[34m$message\e[0m" ;;
    "magenta") echo -e "\e[35m$message\e[0m" ;;
    *) echo "$message" ;;
  esac
}

# Check if Docker is installed
check_docker() {
  if ! command -v docker &> /dev/null; then
    print_message "red" "Docker is not installed. Please install Docker first."
    print_message "yellow" "You can install Docker in WSL Ubuntu with:"
    echo "sudo apt update"
    echo "sudo apt install -y apt-transport-https ca-certificates curl software-properties-common"
    echo "curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg"
    echo "echo \"deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable\" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null"
    echo "sudo apt update"
    echo "sudo apt install -y docker-ce docker-ce-cli containerd.io"
    echo "sudo usermod -aG docker $USER"
    print_message "yellow" "After installation, log out and log back in to apply group changes."
    exit 1
  fi

  if ! command -v docker-compose &> /dev/null; then
    print_message "red" "Docker Compose is not installed. Please install Docker Compose first."
    print_message "yellow" "You can install Docker Compose in WSL Ubuntu with:"
    echo "sudo curl -L \"https://github.com/docker/compose/releases/download/v2.24.5/docker-compose-$(uname -s)-$(uname -m)\" -o /usr/local/bin/docker-compose"
    echo "sudo chmod +x /usr/local/bin/docker-compose"
    exit 1
  fi
}

# Check if user can run docker without sudo
check_docker_permissions() {
  if ! docker info &> /dev/null; then
    print_message "red" "Current user cannot run Docker commands without sudo."
    print_message "yellow" "Either run this script with sudo or add your user to the docker group:"
    echo "sudo usermod -aG docker $USER"
    print_message "yellow" "After adding to group, log out and log back in for changes to take effect."
    read -p "Try to continue anyway? (y/n): " continue_anyway
    if [[ $continue_anyway != "y" ]]; then
      exit 1
    fi
  fi
}

# Function to create environment file
create_env_file() {
  local mode=$1
  
  if [ -f .env ]; then
    read -p "Environment file (.env) already exists. Overwrite? (y/n): " overwrite
    if [[ $overwrite != "y" ]]; then
      print_message "yellow" "Using existing environment file."
      return
    fi
  fi
  
  cp .env-example .env
  print_message "green" "Created environment file from template."
  
  if [ "$mode" == "dev" ]; then
    # Update for development mode
    sed -i 's/DEV_MODE=false/DEV_MODE=true/' .env
    sed -i 's/VLLM_ENABLED=true/VLLM_ENABLED=false/' .env
    sed -i 's/WEAVIATE_ENABLED=true/WEAVIATE_ENABLED=false/' .env
  else
    # Update for production mode
    sed -i 's/DEV_MODE=true/DEV_MODE=false/' .env
    sed -i 's/VLLM_ENABLED=false/VLLM_ENABLED=true/' .env
    sed -i 's/WEAVIATE_ENABLED=false/WEAVIATE_ENABLED=true/' .env
    
    # Generate a random secret key
    SESSION_SECRET=$(openssl rand -hex 32)
    sed -i "s/SESSION_SECRET=change_this_to_a_secure_random_string_in_production/SESSION_SECRET=$SESSION_SECRET/" .env
  fi
}

# Function to check system resources
check_system_resources() {
  local mode=$1
  
  # Get available RAM in MB
  local available_ram=$(free -m | awk '/^Mem:/{print $7}')
  # Get available disk space in GB
  local available_disk=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
  # Get number of CPU cores
  local cpu_cores=$(grep -c ^processor /proc/cpuinfo)
  
  print_message "blue" "\nSystem Resources:"
  print_message "yellow" "- Available RAM: ${available_ram}MB"
  print_message "yellow" "- Available Disk: ${available_disk}GB"
  print_message "yellow" "- CPU Cores: ${cpu_cores}"
  
  local ram_warning=false
  local disk_warning=false
  
  if [ "$mode" == "full" ]; then
    # Resource requirements for full mode
    if [ $available_ram -lt 8192 ]; then
      print_message "red" "Warning: Less than 8GB RAM available. Full mode may be unstable."
      ram_warning=true
    fi
    
    if [ $available_disk -lt 10 ]; then
      print_message "red" "Warning: Less than 10GB disk space available. Full mode requires more space."
      disk_warning=true
    fi
  else
    # Resource requirements for dev mode
    if [ $available_ram -lt 4096 ]; then
      print_message "red" "Warning: Less than 4GB RAM available. Application may be slow."
      ram_warning=true
    fi
    
    if [ $available_disk -lt 5 ]; then
      print_message "red" "Warning: Less than 5GB disk space available. Consider freeing up space."
      disk_warning=true
    fi
  fi
  
  if [ "$ram_warning" = true ] || [ "$disk_warning" = true ]; then
    read -p "Continue despite resource warnings? (y/n): " continue_anyway
    if [[ $continue_anyway != "y" ]]; then
      print_message "yellow" "Exiting setup. Please free up resources and try again."
      exit 1
    fi
  fi
}

# Function to pull Docker images
pull_docker_images() {
  local mode=$1
  
  print_message "blue" "\nPulling required Docker images..."
  
  docker-compose pull app nginx redis postgres
  
  if [ "$mode" == "full" ]; then
    print_message "yellow" "Pulling additional AI service images (this may take a while)..."
    docker-compose pull weaviate t2v-transformers
  fi
}

# Function to build Docker images
build_docker_images() {
  print_message "blue" "\nBuilding application Docker images..."
  docker-compose build
}

# Function to run the application
run_application() {
  local mode=$1
  
  if [ "$mode" == "dev" ]; then
    print_message "blue" "Starting application in DEVELOPMENT mode (no AI services)..."
    docker-compose up -d app chainlit nginx postgres redis
  else
    print_message "blue" "Starting application in FULL mode (with AI services)..."
    docker-compose up -d
  fi
  
  # Wait for services to be ready
  print_message "yellow" "Waiting for services to start up..."
  sleep 5
  
  # Check if services are running
  if ! docker-compose ps | grep -q "Up"; then
    print_message "red" "Error: Services failed to start. Check docker-compose logs."
    exit 1
  fi
  
  print_message "green" "Application started successfully!"
  print_message "green" "- Web interface: http://localhost:80"
  print_message "green" "- ChainLit UI: http://localhost:8000"
  print_message "green" "- Direct API access: http://localhost:5000"
}

# Function to display helpful commands
show_helpful_commands() {
  print_message "magenta" "\n=== Helpful Commands ==="
  echo "View logs:                  docker-compose logs -f"
  echo "Stop all services:          docker-compose down"
  echo "Restart all services:       docker-compose restart"
  echo "Check service status:       docker-compose ps"
  echo "Shell into app container:   docker-compose exec app bash"
  echo "Clean up all data:          docker-compose down -v"
  echo "Update configuration:       nano .env"
  echo "Run make commands:          make help"
}

# Main script
clear
print_message "blue" "============================================="
print_message "blue" "  Contract Anomaly Detection System Setup"
print_message "blue" "  For WSL Ubuntu"
print_message "blue" "============================================="
print_message "yellow" "This script will help you set up and run the application."

# Check prerequisites
print_message "blue" "\nChecking prerequisites..."
check_docker
check_docker_permissions
print_message "green" "Docker and Docker Compose are installed and ready."

# Explain the modes
print_message "blue" "\nAvailable modes:"
print_message "yellow" "1. DEVELOPMENT mode - No AI services (faster, less resources)"
print_message "yellow" "   - Uses mock AI service responses"
print_message "yellow" "   - Stores documents in SQLite database"
print_message "yellow" "   - Minimal resource requirements"
print_message "yellow" ""
print_message "yellow" "2. FULL mode - With all AI services (requires more resources)"
print_message "yellow" "   - Uses Weaviate vector database"
print_message "yellow" "   - Uses vLLM for AI inference"
print_message "yellow" "   - Requires 8GB+ RAM and 10GB+ disk space"

# Prompt for mode
while true; do
  read -p "Select mode (1 or 2): " mode_choice
  case $mode_choice in
    1) 
      mode="dev"
      break 
      ;;
    2) 
      mode="full"
      break 
      ;;
    *) 
      print_message "red" "Invalid choice. Please enter 1 or 2." 
      ;;
  esac
done

# Check system resources
check_system_resources "$mode"

# Create environment file
create_env_file "$mode"

# Pull Docker images
pull_docker_images "$mode"

# Build Docker images
build_docker_images

# Run the application
run_application "$mode"

# Show helpful commands
show_helpful_commands

print_message "blue" "\nApplication is now running! You can access it at http://localhost"
print_message "yellow" "For more information, refer to the README.md file."

# Check if this is WSL
if grep -q Microsoft /proc/version; then
  print_message "magenta" "\nWe detected you're running in WSL. To open the application in your browser, run:"
  print_message "yellow" "explorer.exe http://localhost"
fi