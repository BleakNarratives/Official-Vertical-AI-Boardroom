import sys
import importlib
import os

def hot_reload_module(module_name: str):
    """
    Forces the Python interpreter to discard its cached runtime memory 
    for a specific module and reload the newly mutated version from disk.
    """
    try:
        if module_name in sys.modules:
            print(f"[*] Module '{module_name}' detected in active memory. Flushing cache...")
            reloaded_module = importlib.reload(sys.modules[module_name])
            print(f"[+] Hot-Reload Successful! New memory address: {hex(id(reloaded_module))}")
            return reloaded_module
        else:
            print(f"[*] Module '{module_name}' not in memory yet. Executing initial import...")
            return importlib.import_module(module_name)
    except Exception as e:
        print(f"[!] Hot-Reload failed for '{module_name}': {str(e)}")
        return None

if __name__ == "__main__":
    # Force the local heuristic fallback by ensuring the key triggers the internal agent loop
    os.environ["OPENAI_API_KEY"] = "mock-key-for-local-testing"
    
    import smarter_scout
    print("[*] Initializing test payload...")
    
    # Run the mutated offline agent logic
    scout_instance = smarter_scout.SmarterScout("Test Target", "high rep 4.7")
    
    # FIXED: Accessing via attribute dot-notation instead of dictionary string brackets
    print(f"Before Reload Pitch: {scout_instance.execute_agent_scout().one_sentence_pitch}")
    
    print("\n--- Triggering Live Reload Logic ---")
    hot_reload_module("smarter_scout")
    
    # Re-import to grab the newly hot-swapped memory frame
    from smarter_scout import SmarterScout
    upgraded_instance = SmarterScout("Test Target", "high rep 4.7")
    print(f"After Reload Pitch: {upgraded_instance.execute_agent_scout().one_sentence_pitch}")
