#!/usr/bin/env python3

''' This utility sends an image using the application prex channel to be
displayed at the prex client's terminal.

For example, a prex client may run a C++ program. The C++ program may generate
an image, and use this utility to send the generated image back to the prex
client (via the prex server), to be displayed on the web-app.
'''

import prex
import websockets
import argparse
import os

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('image_file', help="The image file to send to prex.")
    args = parser.parse_args()
    image_file = args.image_file

    image_format = os.path.splitext(image_file)[1].to_upper()

    channel = prex.PrexChannel()

    with open(image_file, 'r') as f:
        data = f.read()
    channel.image(data, image_format) 

if __name__ == '__main__':
    main()
