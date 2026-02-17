# Hardware node code
This is the code for the hardware node.

## Project structure
The file structure used for this the following one :
```
node/
├── build/
│
├── node.ino
│
├── Makefile
└── README.md
```
The `build/` folder will contain the compiled code.

## Compilation
### Create the `secrets.h` file
Copy `secrets_example.h` into `secrets.h` and set the values.

### Edit the board and port
Change the variables `FQBN` (board type) and `PORT` accordingly to your values.

You can use
```bash
arduino-cli board list
# Or
make list
```
in order to see the plugged devices.

### Build the project
Run `make` (or `make upload`) to build and upload the project.

To only build, run `make compile`.

### Other commands
To clean: `make clean` cleans the `build/<board_type>` folder, where `<board_type>` is the folder corresponding to the current value of `FQBN`.

To remake: `make remake` cleans, compiles, and uploads.

To launch the monitor console, run
```
make monitor
```
