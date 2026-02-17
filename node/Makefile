#=============================
#
# Author      : Lasercata
# Last update : 2025.10.20
# Version     : v1.0.0
#
# This is an Arduino makefile.
#
#=============================

# ====== Initialisation ======{{{1
# ------ Port and board ------
# *** Board type ***
# FQBN = arduino:avr:uno
FQBN = esp8266:esp8266:nodemcuv2

# *** Board port ***
# PORT = /dev/ttyACM0
PORT = /dev/ttyUSB0

# *** Baud rate ***
BAUDRATE=9600

# ------ Target ------
TARGET := $(notdir $(abspath $(CURDIR)))

# ------ Compiler ------
CC = arduino-cli

# ------ Other ------
# Name of a compiled file
BUILD_BOARD_DIR = $(subst :,.,$(FQBN))
BUILD_FILE = build/$(BUILD_BOARD_DIR)/$(TARGET).ino.bin
# }}}1

# ====== Rules ======{{{1
# ------ All ------{{{2
.PHONY: all
all: upload
# }}}2

# ------ Compile ------{{{2
.PHONY: compile
compile: $(BUILD_FILE)

$(BUILD_FILE): $(TARGET).ino
	$(CC) compile --export-binaries --fqbn $(FQBN) $<
#}}}2

# ------ Upload ------{{{2
.PHONY: upload
upload: $(BUILD_FILE)
	$(CC) upload --fqbn $(FQBN) -p $(PORT) $(TARGET).ino
#}}}2

# ------ Remake ------{{{2
.PHONY: remake
remake: clean all
#}}}2

# ------ Monitor ------{{{2
.PHONY: monitor
monitor:
	$(CC) monitor -p $(PORT) -c baudrate=$(BAUDRATE)
#}}}2

# ------ List ------{{{2
.PHONY: list
list:
	$(CC) board list
#}}}2

# ------ Clean ------{{{2
.PHONY: clean
clean:
	rm -rf build/$(BUILD_BOARD_DIR)/
#}}}2
# }}}1

# vim:foldmethod=marker:foldlevel=0
