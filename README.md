# Quantum Face Match

A facial recognition app that captures your face and matches you to a famous figure in the quantum computing world, then shows you a video about their history and background.


## Overview

Using OpenCV, the app detects and encodes a live image of your face and compares it against a curated database of notable quantum figures. Your closest match is returned along with a short biographical video.


## Categories

Each person in the database is tagged under one of three categories:

- **Scientist** — Researchers and physicists who shaped the science of quantum mechanics
- **Entrepreneur** — Founders and visionaries who built companies in the quantum space
- **Engineer** — Hardware designers and builders driving quantum systems forward

## Database

Each entry is indexed with a name, category, face encoding, profile image, and a linked bio video covering their contributions and history.


## How It Works

1. Camera captures a live image of the user
2. OpenCV detects and extracts the face
3. Face is encoded into an embedding vector
4. Embedding is compared against the database
5. Closest match is returned with their category and bio video