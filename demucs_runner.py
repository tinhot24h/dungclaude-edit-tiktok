"""Runs Demucs the same way as the `demucs` command, but saves the stems with soundfile.

New torchaudio releases (2.9+) can no longer save WAV files without the extra torchcodec package, which made
Demucs stop at the very end with an error. soundfile has no such dependency, so the output is written with it
whenever it is installed. Usage: python demucs_runner.py <the usual demucs arguments>
"""
import sys


def main(argv):
    import demucs.separate as separate
    try:
        import soundfile
    except ImportError:
        soundfile = None
    if soundfile is not None:
        from demucs.audio import prevent_clip

        def save_audio(wav, path, samplerate, *args, clip='rescale', bits_per_sample=16, as_float=False, **kwargs):
            wav = prevent_clip(wav, mode=clip)
            soundfile.write(str(path), wav.detach().cpu().t().numpy(), samplerate, subtype='FLOAT' if as_float else f'PCM_{bits_per_sample}')

        separate.save_audio = save_audio
    separate.main(argv)


if __name__ == '__main__':
    main(sys.argv[1:])
