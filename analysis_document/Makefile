# ====== Target ======{{{1
TARGET = IoT_Smart_parking_for_disabled_people
# }}}1

# ====== Initialisation ======{{{1
# ------ Compiler ------
CC = pdflatex

SRC_LST = ${wildcard sections/*.tex}

SRC_DIR = sections
# }}}1

# ====== Rules ======{{{1
# ------ All ------{{{2
.PHONY: all
all: $(TARGET).pdf
# }}}2

# ------ Target ------{{{2
$(TARGET).pdf: $(TARGET).tex $(SRC_LST)
	@echo ====== Compiling $@ ======
	$(CC) $<
	$(CC) $<
# }}}2

# ------ Remake ------{{{2
.PHONY: remake
remake: clean-all all
# }}}2

# ------ Clean ------{{{2
.PHONY: clean
clean:
	@echo ====== Cleaning ======
	@rm -f *.aux
	@rm -f *.log
	@rm -f *.nav
	@rm -f *.out
	@rm -f *.snm
	@rm -f *.toc
	@rm -f *.loa
	@rm -f *.lot
	@rm -f *.lol
	@rm -f *.synctex.gz
	@rm -f *.synctex\(busy\)

# ------ Clean pdf ------
.PHONY: clean-pdf
clean-pdf:
	@echo ====== Cleaning $(TARGET).pdf ======
	rm -f $(TARGET).pdf

# ------ Clean all ------
.PHONY: clean-all
clean-all: clean clean-pdf
# }}}2
# }}}1

# vim:foldmethod=marker:foldlevel=0
