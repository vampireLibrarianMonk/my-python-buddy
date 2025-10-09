# HIGH: Unused import (confidence ~90%)
import math  # not referenced anywhere


# MEDIUM: Function defined but never called (confidence ~60%)
# CRITICAL: Unreachable code after return (confidence 100%)
def critical_example():
    return "done"
    print("this line is unreachable")  # dead code
