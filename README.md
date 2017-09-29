# WorstCaseStackAnalyser

Inspired by [Peter McKinnis's version](https://github.com/PeterMcKinnis/WostCaseStack "Check out Peter McKinnis's repository")

NOTE: This is an initial release so it is highly **experimental**!

This little tool statically analyzes the stack requirements of your C programs.  
It is intended to be used on embedded projects.

---

## Requirements
In order for the tool to work you need to ensure the following:  
    * Have Python 3
    * Build your codebase with arm-none-eabi-gcc
    * Compile with -fstackusage and -fdump-rtl-dfinish
    * DO NOT ENABLE Link Time Optimization

## Usage
    `python3 WorstCaseStackAnalyzer.py directory1 [directory2] [...]`

Simply point this tool to your build directory and it will analyze the data for you.
If you have libraries that your program depends on compile them as described above and pass their build folders as well.


Example output:
    Translation Unit	Function Name	Stack	Unresolved Dependencies
    main			main		  104	memcpy
    main			compute		   44

The output is a table of four columns
    Translation Unit:
        The c file
    Function Name:
        Pretty obvious
    Stack:
        Amount of stack used in bytes. "unbounded" if the stack is dynamically allocated and thus cannot be determined faithfully.
    Unresolved Dependencies:
        Functions that are called in this function, yet are not defined in the directory(ies) you pointed to.
        Any time you see unresolved dependencies the stack measurement cannot be relied on.
        To get rid of these you need to compile any dependencies as stated above and include the directory in your call to this tool.

---

## TODO
    * Improve output
    * Cleanup code
    * Make it work for non-embedded codebases as well
    * Better error handling
    * Improve user interface
    * Allow non-recursive directory parsing
    * Support compilers other than arm-none-eabi-gcc

## KNOWN ISSUES
    * Compiling with gcc does not work
