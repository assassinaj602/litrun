CC ?= gcc
CFLAGS ?= -std=c99 -Wall -Wextra -pedantic -O2 -fPIC
CPPFLAGS += -Iinclude

SRCDIR = .
OBJDIR = build
BINDIR = bin
LIBDIR = lib

SOURCES = fingerprint/fingerprint.c governor/governor.c
OBJECTS = $(OBJDIR)/fingerprint.o $(OBJDIR)/governor.o

TARGET_LIB = $(LIBDIR)/liblitrun_core.so
TARGET_PROBE = $(BINDIR)/litrun-probe
TARGET_TEST_FP = $(BINDIR)/test_fingerprint
TARGET_TEST_GOV = $(BINDIR)/test_governor

.PHONY: all lib test clean

all: $(TARGET_LIB) $(TARGET_PROBE)

$(OBJDIR):
	mkdir -p $(OBJDIR)

$(BINDIR):
	mkdir -p $(BINDIR)

$(LIBDIR):
	mkdir -p $(LIBDIR)

$(OBJDIR)/fingerprint.o: fingerprint/fingerprint.c include/fingerprint.h | $(OBJDIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(OBJDIR)/governor.o: governor/governor.c include/governor.h | $(OBJDIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) -c $< -o $@

$(TARGET_LIB): $(OBJECTS) | $(LIBDIR)
	$(CC) -shared $(OBJECTS) -o $@

$(TARGET_PROBE): tools/probe_main.c $(OBJECTS) | $(BINDIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) tools/probe_main.c $(OBJECTS) -o $@

$(TARGET_TEST_FP): ../tests/core/test_fingerprint.c $(OBJECTS) | $(BINDIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) $< $(OBJECTS) -o $@

$(TARGET_TEST_GOV): ../tests/core/test_governor.c $(OBJECTS) | $(BINDIR)
	$(CC) $(CFLAGS) $(CPPFLAGS) $< $(OBJECTS) -o $@

test: $(TARGET_TEST_FP) $(TARGET_TEST_GOV)
	@echo "--- Running C Unit Tests ---"
	./$(TARGET_TEST_FP)
	./$(TARGET_TEST_GOV)
	@echo "All C unit tests passed successfully!"

clean:
	rm -rf $(OBJDIR) $(BINDIR) $(LIBDIR)
