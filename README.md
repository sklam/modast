# Mod-AST

**DO NOT USE! HIGHLY EXPERIMENTAL HOBBY PROJECT**

A tool to modify AST and save into .pyc.

Possible use:

- inject runtime type checks (currently the only feature)


## Software requirement

```
conda install watchdog
```

or 

```
pip install watchdog
```

## How to use?

Install and run the following on the source directory to active 
the watchdog that listens to every `.py` file modication and 
trigger `modast` to insert type checks into the `.pyc` files:

```bash
python -m modast.daemon <source directory>
```
