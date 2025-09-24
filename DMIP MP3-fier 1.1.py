import os
import urllib.parse as ulib
import time

# DMIP MP3-fier Stable Release!

#================================================================================================================================================================#

TPQN = 480  # ticks per quarter note (midi timing thing)

#================================================================================================================================================================#
# Helpers

def vlq(n: int) -> bytes:
    stack = [n & 0x7F]
    n >>= 7
    while n:
        stack.append((n & 0x7F) | 0x80)
        n >>= 7
    return bytes(reversed(stack))

def u32be(n: int) -> bytes:
    return n.to_bytes(4, "big")

def u16be(n: int) -> bytes:
    return n.to_bytes(2, "big")

#================================================================================================================================================================#
# System Exclusives Encoders

# Payload to ASCII Converter (for System Exclusive Message)
def build_dkpayload_sysex(track_name: str, length_delay: float, length_s: int, fade_In: float, fade_Out: float, songspeed: float, uri: str) -> bytes:
    encoded_uri = ulib.quote(uri, safe=":/?&=._-")
    payload = f"dmipv1://playURITrack?track={track_name}&startTime={float(length_delay)}&endTime={int(length_s)}&crossfade_In={float(fade_In)}&crossfade_Out={float(fade_Out)}&speed={float(songspeed)}&uri={encoded_uri}"
    payload_bytes = payload.encode("ascii", "strict")

    man_id, device, tag_type = 0x7D, 0x01, 0x10
    data = bytes([man_id, device, tag_type]) + payload_bytes + b"\xF7"
    return vlq(0) + b"\xF0" + vlq(len(data)) + data
# Tempo
def build_meta_tempo(bpm: float) -> bytes:
    return vlq(0) + b"\xFF\x51\x03" + int(round(60_000_000 / bpm)).to_bytes(3, "big")
# MIDI Chunks
def build_meta_eot(delta_ticks: int) -> bytes:
    return vlq(delta_ticks) + b"\xFF\x2F\x00"
# MIDI Note On Events
def build_note_on(channel: int, note: int, velocity: int, delta: int = 0) -> bytes:
    return vlq(delta) + bytes([(0x90 | (channel & 0x0F)), note & 0x7F, velocity & 0x7F])
# MIDI Note Off Events
def build_note_off(channel: int, note: int, velocity: int, delta: int = 0) -> bytes:
    return vlq(delta) + bytes([(0x80 | (channel & 0x0F)), note & 0x7F, velocity & 0x7F])
# MIDI Chunk Creator/Silence
def make_track_chunk(main_uris: list, vocal_uris: list, bpm: float, length_delay: float, length_s: float, fade_In: float, fade_Out: float, songspeed: float) -> bytes:
    trk = bytearray()
    trk += build_meta_tempo(bpm)

    # sysex dk main payloads - all use "main" as track name
    for main_uri in main_uris:
        trk += build_dkpayload_sysex("main", float(length_delay), int(length_s), float(fade_In), float(fade_Out), float(songspeed), main_uri)

    # sysex dk vocal payloads - all use "vocal" as track name
    for vocal_uri in vocal_uris:
        trk += build_dkpayload_sysex("vocal", float(length_delay), int(length_s), float(fade_In), float(fade_Out), float(songspeed), vocal_uri)

    # Silent Note
    trk += build_note_on(0x0F, 0, 1, delta=0)
    trk += build_note_off(0x0F, 0, 0, delta=int(round(length_s * (TPQN * bpm) / 60.0)))

    # End of Track Event
    trk += build_meta_eot(0)
    return bytes(trk)
# Others
def wrap_chunk(tag: bytes, data: bytes) -> bytes:
    return tag + u32be(len(data)) + data
# SMF Builder
def build_smf_type0(main_uris: list, vocal_uris: list, bpm: float, length_delay: float, length_s: float, fade_In: float, fade_Out: float, songspeed: float) -> bytes:
    hdr = b"MThd" + u32be(6) + u16be(0) + u16be(1) + u16be(TPQN)
    trk = wrap_chunk(b"MTrk", make_track_chunk(main_uris, vocal_uris, bpm, length_delay, length_s, fade_In, fade_Out, songspeed))
    return hdr + trk
# Before Main
def collect_uris(uri_type: str) -> list:
    uris = []
    while True:
        uri = input(f"Enter {uri_type.upper()} Roblox URI (Example: rbxassetid://676769694141): ").strip()
        if not uri:
            print("Invalid Input, try adding rbxassetid:// first.\nIf you don't want to add any main tracks and just only want to add just the vocal track, just type 'rbxassetid://0'.")
            continue
        if not uri.startswith("rbxassetid://"):
            print("Invalid Input, try adding rbxassetid:// first!")
            continue
        uris.append(uri)
        
        more = input(f"Do you want to add more {uri_type.upper()} Roblox URI? (Y or just Enter to skip) ").strip().lower()
        if more != 'y':
            break
    return uris

#================================================================================================================================================================#
# Main (User Friendly CLI Displayer here!)
def main():
    print("Dan's Karaoke DMIP MP3-fier Tool v1.1\n")
    print("===============================================\n")
    print("Changelogs: Last Updated around 31.8.2025")
    print("- Added option to modify fade-ins and fade-outs (with a maximum value of 10 seconds)\n- Added option to delay the startup time (It also accepts negative values and decimal points if you want to sync it with an existing MIDI!)\n- Added option to speed up or slow down song duration.\n- Default filename is now named 'My DMIP MP3-fied Song.mid'\n- Entering less than or equal to 0BPM or exceeding above 512BPM will no longer work.\n- Entering less than or equal to 0 second in song duration will no longer work.\n- Program closing duration has been decreased to 15 seconds.")
    print("\n===============================================\n")

    # Collect main URIs (Allows Repetition)
    main_uris = collect_uris("main")
    
    # Collect vocal URIs (Allows Repetition)
    vocal_uris = []
    add_vocal = input("Do you want to also add or add more VOCAL Roblox URI? (Y or just Enter to skip): ").strip().lower()
    if add_vocal == 'y':
        vocal_uris = collect_uris("vocal")

    # Beats Per Minute
    while True:
        bpm_in = input("\nEnter BPM/Tempo (By default, it is '120'): ").strip()
        if not bpm_in:
            bpm = 120
            break
        try:
            bpm = float(bpm_in)

            if bpm <= 0:
                print("Error. BPM cannot go below 0BPM. Try again.")
            elif bpm > 512:
                print("Error. BPM cannot exceed more than 512BPM, no songs exists with that tempo.")
            else:
                break

        except ValueError:
            print("Error. It's either not a number or you incorrectly entered the Tempo.")

    # Song Length (Only Accepts Seconds)
    while True:
        length_in = input("\nEnter Song Length (in seconds): ").strip()
        try:
            length_s = float(length_in)
            if length_s <= 0:
              print("Song Length cannot go below than 0 second. Try again.")
            else:
                break
        except ValueError:
            print("Not a second. And If you typed something like 1:30, its not correct. It must be STRICTLY IN SECONDS \n(Tip: To convert Minutes+Seconds into Seconds, multiply 60 x minutes then sum it to the seconds of the song.)")

    # Song Delay (Accepts Seconds in Decimal Values)
    while True:
        startTime = input("\nEnter Song Delay/Start Time in seconds (By default, it is '0'. It also accepts negative and decimal values!): ").strip()
        if not startTime:
            length_delay = 0
            break
        try:
            length_delay = float(startTime)
            break
        except ValueError:
            print("Not a second. And If you typed something like 1:30, its not correct. It must be STRICTLY IN SECONDS \n(Tip: To convert Minutes+Seconds into Seconds, multiply 60*minutes then sum it to the seconds of the song)")

    # Crossfade In
    while True:
        cfIn = input("\nEnter 'Fade In' in seconds (By default, it is '0'. It must NOT exceed by 10 seconds. It also accepts negative and decimal values!): ").strip()
        if not cfIn:
            fade_In = 0
            break
        try:
            fade_In = float(cfIn)
            if fade_In <= -1:
                print("Error. Crossfade In cannot exceed below negative seconds.")
            elif fade_In > 10:
                print("Error. Crossfade In must NOT exceed by 10 seconds.")
            else:
                break
        except ValueError:
            print("Not a second, try again.")

    # Crossfade Out
    while True:
        cfOut = input("\nEnter 'Fade Out' in seconds (By default, it is '0'. It must NOT exceed by 10 seconds. It also accepts negative and decimal values!): ").strip()
        if not cfOut:
            fade_Out = 0
            break
        try:
            fade_Out = float(cfOut)
            if fade_Out <= -1:
                print("Error. Crossfade Out cannot exceed below negative seconds. Try again.")
            elif fade_Out > 10:
                print("Error. Crossfade Out must NOT exceed by 10 seconds. Try again.")
            else:
                break
        except ValueError:
            print("Error. Not a second, try again.")

    # Speed
    while True:
        s_speed = input("\nEnter 'Song Speed' (By default, it is set as '1'): ").strip()
        if not s_speed:
            songspeed = 1
            break
        try:
            songspeed = float(s_speed)
            break
        except ValueError:
            print("Error. Not a number, try again.")

    # Output file 
    out_file = input("\nOutput Filename (by default, it is 'My DMIP MP3-fied Song.mid'): ").strip() or "My DMIP MP3-fied Song.mid"

    try:
        midi = build_smf_type0(main_uris, vocal_uris, bpm, length_delay, length_s, fade_In, fade_Out, songspeed)
        with open(out_file, "wb") as f:
            f.write(midi)
        print(f"\nSuccess! Access your file at: {os.path.abspath(out_file)}\nand then, upload the file on Dan's Karaoke.")
    except Exception as e:
        print("An error has occured. Please check if you have entered everything correctly.\n\nError will be printed out below:\n", e)

    finally:
        print(f"\nIf you have any questions, create a forum in our Discord Server at discord.gg/DansKaraoke!\n")
        print(f"If the audio did not work, check for errors by pressing F9 console inside Dan's Karaoke Game.")
        print(f"If it says anything related to 'User is not authorized to access asset', its either:\n(1)You used your own uploaded MP3 audio, in which it requires to add Daniel as collaborator.\n(2)You made a typo in entering the asset ID.\n(3)You made a typo or added a decimal point.")
    for i in range(15, -1, -1):
        print(f"\nThis program will close automatically in {i} seconds... ", end='\r', flush=True)
        time.sleep(1)
#================================================================================================================================================================#

if __name__ == "__main__":
    main()

#================================================================================================================================================================#

# CHANGELOGS HISTORY

# DMIP MP3-fier version 1.1 Changelogs! (August 31 2025)
# -Added option to modify fade-ins and fade-outs (with a maximum value of 10 seconds)
# -Added option to delay the startup time (It also accepts negative values and decimal points if you want to sync it with an existing MIDI!)
# -Added option to speed up or slow down song duration.
# -Default filename is now named "My DMIP MP3-fied Song.mid"
# -Entering less than or equal to 0BPM or exceeding above 512BPM will no longer work.
# -Entering less than or equal to 0 second in song duration will no longer work.
# -Program closing duration has been decreased to 15 seconds.

# DMIP MP3-fier version 1.0 Changelogs! (August 29 2025)
# -It supports multiple audio with no problems by making another System Exclusive messages.
# -The text is more user-friendly now than it does before.
# -Fixed an issue where the program would close unexpectedly without displaying the status message whether it is successful or not.
# (Dani just wrote the code very quickly that he forgot to add time.sleep(1) lol)
# -Instruction note can instruct a noob :money_mouth:
