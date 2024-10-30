import pickle
import os

def load_results(file_path):
    """Load results from a pickle file."""
    with open(file_path, 'rb') as file:
        return pickle.load(file)

def print_results(label, results):
    """Print the results with a label."""
    print(f"\n--- {label} ---")
    print(results)

def main():
    # Define the directory where the .pckl files are located
    data_dir = 'data/work/pywork/example'  # Change this if your path is different

    # List of result files to load
    result_files = {
        'Active SD': 'activesd.pckl',
        'Faces': 'faces.pckl',
        'Scene': 'scene.pckl',
        'Tracks': 'tracks.pckl'
    }

    # Load and print results for each file
    for label, filename in result_files.items():
        file_path = os.path.join(data_dir, filename)
        if os.path.exists(file_path):
            results = load_results(file_path)
            print_results(label, results)
        else:
            print(f"{label} file not found at {file_path}")

if __name__ == "__main__":
    main()
