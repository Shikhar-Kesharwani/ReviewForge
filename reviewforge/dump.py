"""
reviewforge/dump.py

Debug utility for ReviewForge.
Prints variable names and their values to stderr during development.
Usage:
    from reviewforge.dump import dump
    dump(my_var, another_var)
"""

import inspect
import sys


def dump(*vals):
    """
    Print each value with its inferred variable name to stderr.

    Walks the caller's frame to extract the source-level names passed
    as arguments.  Useful for quick debug inspection without a full
    debugger session.

    Example
    -------
    >>> x = 42
    >>> y = "hello"
    >>> dump(x, y)
    x = 42
    y = hello
    """
    # Walk one frame up to reach the caller
    frame = inspect.currentframe()
    try:
        caller_frame = frame.f_back
        # Retrieve the source line that called dump(...)
        try:
            # inspect.getframeinfo returns a named-tuple with code_context
            frame_info = inspect.getframeinfo(caller_frame)
            source_lines = frame_info.code_context
            if source_lines:
                # The raw call line, e.g. '    dump(x, y, result)\n'
                call_line = source_lines[0].strip()
                # Extract the argument text between the outer parentheses
                # of 'dump(...)'.
                start = call_line.find("dump(")
                if start != -1:
                    inner = call_line[start + len("dump("):]
                    # Find matching closing parenthesis (handles nested parens)
                    depth = 1
                    end = 0
                    for i, ch in enumerate(inner):
                        if ch == "(":
                            depth += 1
                        elif ch == ")":
                            depth -= 1
                            if depth == 0:
                                end = i
                                break
                    arg_text = inner[:end]
                    # Split on commas (naïve but fine for simple variable names)
                    arg_names = [a.strip() for a in arg_text.split(",")]
                else:
                    arg_names = []
            else:
                arg_names = []
        except Exception:
            arg_names = []

        # Print each value paired with its name (or a placeholder)
        for idx, val in enumerate(vals):
            name = arg_names[idx] if idx < len(arg_names) else f"arg{idx}"
            print(f"{name} = {val!r}", file=sys.stderr)
    finally:
        # Always delete the frame reference to avoid reference cycles
        del frame
