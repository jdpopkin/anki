# Linux

## Requirements

These instructions are written for Debian/Ubuntu; adjust for your distribution.
Some extra notes have been provided by a forum member:
https://forums.ankiweb.net/t/guide-how-to-build-and-run-anki-from-source-with-xubuntu-20-04/12865

Glibc is required - if you are on a distro like Alpine that uses musl, you'll need
to contribute fixes to the upstream [Rust rules](https://github.com/bazelbuild/rules_rust/issues/390),
then follow the steps in [Other Platforms](./new-platform.md).

**Ensure some basic tools are installed**:

```
$ sudo apt install bash grep findutils curl gcc g++ git
```

The 'find' utility is 'findutils' on Debian.

**Python**:

For building and running from source, Python is required, but the version is
flexible - any version from 2.7 onwards should work. The build system expects to
find the command `python`, so if your system only has a `python3`, you'll need
to link it to `python`, or do something like `sudo apt install python-is-python3`.

The system Python is only used for running scripts, and the build system will
download a copy of Python 3.9 into a local folder as part of the build.

You can have it use a locally installed Python instead, by putting something
like the following into a file called user.bazelrc at the top of this repo
before proceeding:

```
build --action_env=PYO3_PYTHON=/usr/local/bin/python3.9
```

**Install Bazelisk**:

Download it under the name 'bazel':

```
$ curl -L https://github.com/bazelbuild/bazelisk/releases/download/v1.10.1/bazelisk-linux-amd64 -o ./bazel
```

And put it on your path:

```
$ chmod +x bazel && sudo mv bazel /usr/local/bin/
```

## Running Anki during development

From the top level of Anki's source folder:

```
./run
```

This will build Anki and run it in place.

The first build will take a while, as it downloads and builds a bunch of
dependencies. When the build is complete, Anki will automatically start.

The Javascript build code is currently a bit flaky, so the initial
build may fail with an error. If you get an error when running/building,
try repeating the command once or twice - it should pick up where it left off.

To play and record audio, install mpv and lame.

If you or your distro has made ccache the standard compiler, you will need to
set CC and CXX to point directly to gcc/g++ or clang/clang++ prior to building
Anki.

## Missing Libraries

If you get errors during startup, try starting with

QT_DEBUG_PLUGINS=1 ./run

It will likely complain about missing libraries, which you can install with
your package manager. Some of the libraries that might be required on Debian
for example:

```
sudo apt install libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
  libxcb-randr0 libxcb-render-util0
```

## Optimized builds

The `./run` command will create a non-optimized build by default. This is faster
to compile, but will mean Anki will run considerably slower.

To run Anki in optimized mode, use:

```
./scripts/runopt
```

## More

For info on running tests, building wheels and so on, please see [Development](./development.md).
