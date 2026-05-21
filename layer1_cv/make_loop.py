import subprocess

# Loop video 10x pakai ffmpeg langsung
subprocess.run([
    'ffmpeg', '-y',
    '-stream_loop', '9',
    '-i', 'tests/output_result.mp4',
    '-c', 'copy',
    'tests/loop_result.mp4'
])
print('Done!')