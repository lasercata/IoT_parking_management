# IoT smart parking -- Instructions to compile the document

## Dependencies
You need to have `pdflatex` installed on your machine.

## Create `data.sty`
Create `data.sty`:
```
cp data/data_template.sty data/data.sty
```

And then edit with the corresponding values.

## Compile
You can use the makefile to compile:
```
make
```

To remove the generated files:
```
make clean
```

