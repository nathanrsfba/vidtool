vidtool
=======

vidtool is a Python script that is basically a frontend for some common
video/audio tasks that I use in my own videos.

The general syntax is:

```
vidtool command [options]
```

where `command` is the task to run, and `options` are the options for the task.

`vidtool` depends on `ffmpeg(1)` for most of its tools. It depends on `fdkaac(1)` for
the `aacenc` and `audiomix` functions, and `sox(1)` for the `compand` function.

Common Options
--------------

Many of the subcommands support a common set of options:

* `-f`: If the specified output file already exists, it is deleted and
  overwritten. Without this option, the program will exit with an error if the
  specified output file already exists.
* `-h`: Get help on the given subcommand. 

Commands
--------

### help ###

```
vidtool help [command]
```

Displays a list of commands, or shows help for a particular command.

Specifying a command shows help on that command. This is generally equivalent to calling the command with the `-h` option.

### mixdown ###

```
mixdown [-h] [-f] input [input ...] output
```

`mixdown` mixes a series of `.wav` files down into a single file.

`input` specifies the input file(s), `output` specifies the file to create.

### aacenc ###

```
aacenc [-h] [-f] input [output]
```

`aacenc` will encode a `wav` file into AAC format.

`input` and `output` are the paths to the input and output files. If `output` is not specified, a filename will be automatically generated based on the input filename.

### remux ###

```
remux [-h] [-f] video audio output
```

Combines the video from one file and audio from a second file into a new video file.

`video` and `audio` specify the files to take the video and audio from. Any audio tracks in the `video` file are ignored. The audio in `audio` is expected to be encoded in the format desired for the final video file.

`output` specifies the output file.

### audiomix ###

```
audiomix [-h] [-f] video audio [audio ...] output
```

This combines the `mixdown`, `aacenc`, and `remux` tasks in a single command. Intermediate files are saved to a temporary directory which is deleted after processing.

`video` specifies the file to take video footage from.

`audio` specifies the file(s) to take audio tracks from. These should be uncompressed `wav` files.

`output` specfies the filename to save combined tracks to.

### scale ###

```
scale [-h] [-f] input size output
```

Scales a video file down to a smaller video resolution. Audio is copied unchanged.

`input` is the file to scale.

`size` is the resolution to scale the video to, in `WIDTH`:`HEIGHT` form. Ex. `1280:720`.

`output` is the name of the file to save the new video to.

### extaudio ###

```
extaudio [-h] [-t TRACK] [-f] input output
```

Extracts a track of audio from a video file.

`input` is the file to extract audio from. `output` is the file to save audio to.

`TRACK` specifies which audio track to extract. It is zero-based: `0` extracts
the first audio track, which is also the default.

This tool extracts the audio track in the original format, unchanged. In
theory, this will result in an audio file identical to its content before
muxing.

### decaudio ###

```
decaudio [-h] [-t TRACK] [-n] [-f] input output
```

Extract and decode audio tracks from a video.

In contrast to `extaudio`, this will both extract an audio track, and convert
it into a different format.  In theory, this can be in any format that `ffmpeg`
can encode, but has only been tested with `wav`. Output format is autodetected
according to the file extension (by `ffmpeg` itself).

This tool can also extract multiple tracks, with each track output to a
separate file.

`input` is the file to extract audio from. `output` is the file to save audio to.

`TRACK` is the numeric index of the audio track to decode: Track 0 is the
first. Specify multiple `-t` options to extract multiple tracks.

`-n` will append the track number to the filename, in between the name and the
extension. Automatically enabled if multuiple tracks specified.

### compgate ###

```
compgate [-h] [-a ATTACK] [-d DECAY] [-s SOFT-KNEE] [-g GAIN]
         [-i INITIAL-VOLUME] [-l DELAY] [-G GATE] [-C COMPRESS]
         [-T TARGET] [-f]
         input output
```

Compress and noise gate an audio file.

The details of dynamic range compressors/expanders ("companders") is beyond the
scope of this document, but the following is a basic explanation.

A dynamic range compresor (or just "compressor") amplifies the quieter sections
of an audio input, and/or attenuates (the opposite of amplify) the louder
sections. The end result is an audio signal which has a more "even" volume:
There is less fluctuation between quieter and louder parts.

A dynamic range expander does the opposite: It makes the quiet parts quieter,
and/or the loud parts louder. A noise gate is a type of expander which takes
this concept to the extreme: It attenuates the quietest parts of an input until
they're effectively inaudible. This has the effect of "cutting out" background
noise. The quietest parts of the signal (which generally consist of *only*
background noise) are removed, while the louder parts (where the desired signal
"drowns out" the noise) are unchanged.

This command is a simple frontend to the `sox` utility that performs both of
the above functions simultaneously.

There are several options that can control this. Most of them accept either a
duration or a volume.

Durations are given in seconds, which may be fractional.

Volumes are given in decibels ('dB'). Decibel is a logarythmic measure of
volume, where 0dB is the loudest possible sound that can be encoded, and
negative infinity is complete silence. Therefore, the volume of a particular
audio segment will be measured in negative decibels, although *changes* in
volume may be measured in either positive or negative decibels.

`input` and `output` specify the source and target files.

`ATTACK` specifies the time to ramp up quiet audio segments. Shorter values
cause quiet segments to quickly be amplified, longer values cause a more
gradual change.

`DECAY` specifies the time to ramp down loud segments. The same logic applies
as with `ATTACK.`

`DELAY` is the time to "look ahead" when adjusting audio levels. This cause
volumes to be raised/lowered *before* quieter/louder segments begin; highest
values cause the adjustment to happen earlier.

`GAIN` specifies the amount to amplify the entire input. This is on top of the
amplification/attenuation applied as part of the companding process.

`INITIAL-VOLUME` specifies the volume at the start of processing.

`GATE` specifies the volume level below which all audio should be removed.

`COMPRESS` specifies the level above which audio should be compressed.

`TARGET` specifies the level which audio at the `COMPRESS` level should be
amplified to.

Audio segments which are quieter than `GATE` will be muted entirely. Audio
segments louder than `GATE` but quieter than `COMPRESS` will be unchanged.
Audio segments louder than `COMPRESS` will be amplified until they are at or
above the `TARGET` level.

`SOFT-KNEE` specifies how much (in dB) to round hard corners in the compander
curve.

