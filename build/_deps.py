# Every module the external app/*.py may import. Listed here so PyInstaller bundles them into the launcher EXE.
# Extra stdlib modules are included on purpose so that future code-only updates can use them without rebuilding the EXE.
import asyncio, base64, bisect, collections, concurrent.futures, csv, ctypes, ctypes.wintypes, dataclasses, datetime  # noqa
import email, functools, glob, gzip, hashlib, heapq, http.client, importlib, io, itertools, json  # noqa
import logging, math, os, pathlib, queue, random, re, shutil, sqlite3, ssl, statistics, string  # noqa
import struct, subprocess, sys, tempfile, textwrap, threading, time, traceback, typing, unicodedata  # noqa
import urllib.parse, urllib.request, uuid, weakref, zipfile, zlib, py_compile, ast, xml.etree.ElementTree  # noqa
from PySide6 import QtCore, QtGui, QtWidgets, QtMultimedia, QtMultimediaWidgets, QtNetwork, QtSvg  # noqa
