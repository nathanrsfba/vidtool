#!/usr/bin/python3

from subprocess import run
from argparse import ArgumentParser
from sys import argv, stderr
from pathlib import Path
from tempfile import TemporaryDirectory
from decimal import Decimal

class vtCommand:
    """Base class for all vidtool commands"""

    commands = {}

    def __init__( self, name, blurb=None ):
        """Initialize the command.

        name -- The name of the command
        blurb -- A short description of the command. If none is provided,
          it is taken from the classes docstring.
        """
        self.name = name
        if blurb:
            self.blurb = blurb
        else:
            self.blurb = self.__class__.__doc__

    def do( self, argsin ):
        """Execute the given command.

        argsin -- A list of arguments to the function
        """
        pass

    def register( self ):
        """Register the command in the list of commands."""
        vtCommand.commands[self.name] = self

    def help( self ):
        """Display help for the command."""
        self.do( ['--help'] )


class vtHelp( vtCommand ):
    """Get help for a command, or a list of commands"""

    def __init__( self ):
        super().__init__( 'help' )

    def do( self, argsin ):
        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'command', nargs='?',
                            help='Command to get help on' )

        args = parser.parse_args( argsin )

        if not args.command:
            print( "Available commands:" )
            for cmd in vtCommand.commands.values():
                print( "%-10s %s" % (cmd.name, cmd.blurb) )
        elif args.command in vtCommand.commands:
            vtCommand.commands[args.command].help()
        else:
            print( f"Invalid command: {args.command}" , file=stderr )
            exit( 1 )
vtHelp().register()

class vtMixdown( vtCommand ):
    """Mix multiple audio files into a single file"""

    def __init__( self ):
        super().__init__( 'mixdown' )

    def do( self, argsin ):
        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'input', nargs='+',
                            help='Input files to mix' )
        parser.add_argument( 'output',
                            help='File to save to' )
        parser.add_argument( '-f', '--force', action='store_true',
                            help="Overwrite existing files" )

        args = parser.parse_args( argsin )

        outpath = Path( args.output )
        checkExists( outpath, args.force )

        self.execute( args.input, args.output )

    @classmethod
    def execute( self, inputs, output ):
        """Execute ffmpeg to downmix the files

        Return: Numeric exit code from ffmpeg
        """

        cmd = ['ffmpeg']
        for f in inputs:
            cmd.append( '-i' )
            cmd.append( f )
        cmd.append( '-filter_complex' )
        cmd.append( f'amix=inputs={len( inputs ) }:duration=first' )
        cmd.append( output )
        result = run( cmd )
        return result.returncode
vtMixdown().register()

class vtAACEnc( vtCommand ):
    """Encode an audio file to AAC"""

    def __init__( self ):
        super().__init__( 'aacenc' ) 

    def do( self, argsin ):
        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'input',
                            help='Input file' )
        parser.add_argument( 'output', nargs='?',
                            help='Output file' )
        parser.add_argument( '-f', '--force', action='store_true',
                            help="Overwrite existing files" )

        args = parser.parse_args( argsin )

        outpath = args.output
        if outpath: 
            outpath = Path( outpath )
            checkExists( outpath, args.force )

        self.execute( args.input, outpath )

    @classmethod
    def execute( self, input, output, quality=None ):
        """Execute fdkaac to encode the file.

        quality -- A numeric quality, 1-5, to specify the encoding quality.
            (Specified with the `-m` option in fdkaac). If not specified,
            defaults to 5.

        Return: Numeric exit code from fdkaac
        """


        cmd = ['fdkaac']
        if not quality: quality = 5
        cmd.extend( ('-m', str( quality )) )

        cmd.append( input )

        if output:
            cmd.extend( ('-o', output) )

        # print( cmd )
        # return 0
        result = run( cmd )
        return result.returncode
vtAACEnc().register()

class vtRemux( vtCommand ):
    """Remux a video file and audio file into a new file""" 
    def __init__( self ):
        super().__init__( 'remux' )

    def do( self, argsin ):
        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'video',
                            help='Input video file. (Any audio tracks are ignored)' )
        parser.add_argument( 'audio', 
                            help='Input audio file. Should be appropriately encoded.' )
        parser.add_argument( 'output', 
                            help='Output video file' )
        parser.add_argument( '-f', '--force', action='store_true',
                            help="Overwrite existing files" )

        args = parser.parse_args( argsin )

        outpath = Path( args.output )
        checkExists( outpath, args.force )
        self.execute( args.video, args.audio, outpath )

    @classmethod
    def execute( self, video, audio, output ):
        """Execute ffmpeg to encode the file.

        Return: Numeric exit code from ffmpeg
        """

        # Remux audio and video:
        # ffmpeg -i <input_video> -i <input_audio> -c copy -map 0:v:0 -map 1:a:0 <output_video>
        cmd = ['ffmpeg', '-i', video, '-i', audio,
               '-c', 'copy', '-map', '0:v:0', '-map', '1:a:0', output]

        # print( cmd )
        # return 0
        result = run( cmd )
        return result.returncode
vtRemux().register()

class vtAudiomix( vtCommand ):
    """Mix a video file with external audio tracks into a new file"""
    def __init__( self ):
        super().__init__( 'audiomix' )

    def do( self, argsin ):
        """Remix the video file.

        This command combines the `mixdown`, `aacenc`, and `remux` commands
        into one. If any of the programs in the pipeline returns a failure
        code, the script is aborted with an error. Intermediate files are saved
        to a temporary directory, which is deleted on exit.
        """

        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'video',
                            help='Input video file. (Any audio tracks are ignored)' )
        parser.add_argument( 'audio', nargs='+',
                            help='Input audio files, in WAV format' )
        parser.add_argument( 'output',
                            help='Output video file' )
        parser.add_argument( '-f', '--force', action='store_true',
                            help="Overwrite existing files" )

        args = parser.parse_args( argsin )

        outpath = Path( args.output )
        checkExists( outpath, args.force )

        with TemporaryDirectory() as tmppath:
            tmp = Path( tmppath )
            print( "Combining audio files..." )
            result = vtMixdown.execute( args.audio, tmp / 'mix.wav' )
            if result:
                print( f"Error running ffmpeg.", file=stderr )
                exit( 1 )
            print( "Encoding audio..." )
            result = vtAACEnc.execute( tmp / 'mix.wav', tmp / 'mix.aac' )
            if result:
                print( f"Error running ffmpeg.", file=stderr )
                exit( 1 )
            print( "Remuxing video..." )
            result = vtRemux.execute( args.video, tmp / 'mix.aac', outpath )
            if result:
                print( f"Error running ffmpeg.", file=stderr )
                exit( 1 )

            # run( '/bin/sh', cwd=tmp )
vtAudiomix().register()

class vtScale( vtCommand ):
    """Scale a video down to a smaller size."""

    def __init__( self ):
        super().__init__( 'scale' )

    def do( self, argsin ):
        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'input',
                            help='Input video file.' )
        parser.add_argument( 'size',
                            help='Size to rescale to, in WIDTH:HEIGHT format' )
        parser.add_argument( 'output',
                            help='Output video file' )
        parser.add_argument( '-f', '--force', action='store_true',
                            help="Overwrite existing files" )

        args = parser.parse_args( argsin )

        outpath = Path( args.output )
        checkExists( outpath, args.force )

        cmd = ['ffmpeg', '-i', args.input,
               '-vf', f"scale={args.size}", 
               '-acodec', 'mp3', '-b:a', '64k', outpath]
        run( cmd )
vtScale().register()

class vtExtractAudio( vtCommand ):
    """Extract an audio track from a file."""

    def __init__( self ):
        super().__init__( 'extaudio' )

    def do( self, argsin ):
        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'input',
                            help='Input video file.' )
        parser.add_argument( 'output',
                            help='Output audio file. Will be extracted from ' +
                            'the original without any transcoding.' )
        parser.add_argument( '-t', '--track', default=0, type=int,
                            help="Number of audio track to extract, zero-based. " +
                            '(Default 0)' )
        parser.add_argument( '-f', '--force', action='store_true',
                            help="Overwrite existing files" )

        args = parser.parse_args( argsin )

        outpath = Path( args.output )
        checkExists( outpath, args.force )

        cmd = ['ffmpeg', '-i', args.input, '-acodec', 'copy', '-map', 
               f'0:a:{args.track}', outpath]
        run( cmd )
vtExtractAudio().register()

class vtDecodeAudio( vtCommand ):
    """Extract and decode audio tracks from a video"""

    def __init__( self ):
        super().__init__( 'decaudio' )

    def do( self, argsin ):
        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'input',
                            help='Input video file.' )
        parser.add_argument( 'output',
                            help='Output audio file. Will be transcoded into ' +
                            'a format appropriate to the given filename.' )
        parser.add_argument( '-t', '--track', action='append', type=int,
                            help="Number of audio track(s) to extract, zero-based. " +
                            'May be specified more than once. (Default 0)' )
        parser.add_argument( '-n', '--number', action='store_true',
                            help="Append track number to filename. Automatically " +
                            'enabled if multuiple tracks specified.' )
        parser.add_argument( '-f', '--force', action='store_true',
                            help="Overwrite existing files" )

        args = parser.parse_args( argsin )
        if not args.track:
            args.track = [0]
        if len( args.track ) > 1:
            args.number = True

        for t in args.track:
            outpath = Path( args.output )
            if args.number:
                outpath = outpath.parent / f"{outpath.stem}{t}{outpath.suffix}"
            checkExists( outpath, args.force )
            cmd = ['ffmpeg', '-i', args.input, '-map', 
               f'0:a:{t}', outpath]
            result = run( cmd )
            if result.returncode:
                return result.returncode
        return 0
vtDecodeAudio().register()

class vtCompGate( vtCommand ):
    """Compress and noise gate an audio file"""

    def __init__( self ):
        super().__init__( 'compgate' )

    def do( self, argsin ):
        parser = ArgumentParser( prog=self.name, description=self.blurb )

        parser.add_argument( 'input',
                            help='Input audio file.' )
        parser.add_argument( 'output',
                            help='Output audio file.' )
        parser.add_argument( '-a', '--attack', type=Decimal, default='.1',
                            help='Attack time (default: %(default)s)' )
        parser.add_argument( '-d', '--decay', type=Decimal, default='.2',
                            help='Decay time (default: %(default)s)' )
        parser.add_argument( '-s', '--soft-knee', type=Decimal, default='6',
                            help='Soft knee in dB (default: %(default)s)' )
        parser.add_argument( '-g', '--gain', type=Decimal, default='-5',
                            help='Gain in dB (default: %(default)s)' )
        parser.add_argument( '-i', '--initial-volume', type=Decimal, default='-90',
                            help='Initial Volume in dB (default: %(default)s)' )
        parser.add_argument( '-l', '--delay', type=Decimal, default='.2',
                            help='Delay time (default: %(default)s)' )
        parser.add_argument( '-G', '--gate', type=Decimal, default='-48',
                            help='Gate threshold in dB (default: %(default)s)' )
        parser.add_argument( '-C', '--compress', type=Decimal, default='-40',
                            help='Compression Threshold in dB (default: %(default)s)' )
        parser.add_argument( '-T', '--target', type=Decimal, default='-20',
                            help='Compression Target in dB (default: %(default)s)' )

        parser.add_argument( '-f', '--force', action='store_true',
                            help="Overwrite existing files" )

        args = parser.parse_args( argsin )

        outpath = Path( args.output )
        checkExists( outpath, args.force )

        # print( args )
        cmd = ['sox', '-S', args.input, args.output,
               'compand',
               f"{args.attack},{args.decay}",
               f"{args.soft_knee}:-inf,{args.gate-Decimal( '.1' )}," +
               f"-inf,{args.gate},{args.gate},"+
               f"{args.compress},{args.target}",
               str( args.gain ), str( args.initial_volume ), 
               str( args.delay ) ]
        # print( cmd )
        result = run( cmd )
        return result.returncode
vtCompGate().register()


def checkExists( path, force=None ):
    """Check if a file already exists.

    path -- The path to check
    force -- Delete the file if it exists

    Checks if the given path-like object exists.

    If force is true, delete the file. If force is false, returns if the file
    does *not* exist, and exits the script with an error and status 1 if the
    file does exist.
    """

    path = Path( path )
    if path.exists():
        if force:
            path.unlink()
        else:
            print( f'{path} already exists. Use -f to overwrite', 
                  file=stderr )
            exit( 1 )

parser = ArgumentParser( prog='vidtool', 
                        description="A frontend for various video/audio fixes" )

parser.add_argument( 'command', 
                    help='Command to perform. (Use `help` for a list)' )
parser.add_argument( 'options', nargs='*',
                    help='Options for the command' )

args = parser.parse_args( argv[1:2] )
if args.command in vtCommand.commands:
    vtCommand.commands[args.command].do( argv[2:] )
else:
    print( f"Invalid command: {args.command}", file=stderr )
    exit( 1 )

# vtCommand.commands['mixdown'].do( argv[1:] )
