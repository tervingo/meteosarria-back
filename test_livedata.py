#!/usr/bin/env python3
"""
Test script to verify that the get_meteohub_parameter function works correctly
with the new timeout settings.
"""

import time
from livedata import get_meteohub_parameter

def test_meteohub_connection():
    """Test the connection to Meteohub with timeout handling."""
    print("Testing Meteohub connection...")
    
    # Test parameters
    parameters = ["ext_temp", "int_temp", "hum", "wind_dir", "wind_speed", "press", "cur_rain", "total_rain", "rad"]
    
    for param in parameters:
        print(f"\nTesting parameter: {param}")
        start_time = time.time()
        
        try:
            value = get_meteohub_parameter(param)
            end_time = time.time()
            duration = end_time - start_time
            
            if value is not None:
                print(f"  ✓ Success: {value} (took {duration:.2f}s)")
            else:
                print(f"  ✗ Failed: No value returned (took {duration:.2f}s)")
                
        except Exception as e:
            end_time = time.time()
            duration = end_time - start_time
            print(f"  ✗ Error: {e} (took {duration:.2f}s)")

if __name__ == "__main__":
    test_meteohub_connection() 