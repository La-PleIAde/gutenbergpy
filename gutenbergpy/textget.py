# -*- coding: utf-8 -*-
# encoding=utf8 
from __future__ import absolute_import, unicode_literals

import gzip
import os
import errno
import http.client
from contextlib import closing
from typing import Union

from future.standard_library import install_aliases
install_aliases()
from urllib.request import urlopen
from urllib.parse import urlparse
import chardet
from gutenbergpy.gutenbergcachesettings import GutenbergCacheSettings

class UnknownDownloadUri(Exception):
    """location cannot be found for a text"""

##
# MARKERS ARE FROM https://github.com/c-w/Gutenberg/blob/master/gutenberg/_domain_model/text.py

TEXT_START_MARKERS = frozenset((
    "*END*THE SMALL PRINT",
    "*** START OF THE PROJECT GUTENBERG",
    "*** START OF THIS PROJECT GUTENBERG",
    "This etext was prepared by",
    "E-text prepared by",
    "Produced by",
    "Distributed Proofreading Team",
    "Proofreading Team at http://www.pgdp.net",
    "http://gallica.bnf.fr)",
    "      http://archive.org/details/",
    "http://www.pgdp.net",
    "by The Internet Archive)",
    "by The Internet Archive/Canadian Libraries",
    "by The Internet Archive/American Libraries",
    "public domain material from the Internet Archive",
    "Internet Archive)",
    "Internet Archive/Canadian Libraries",
    "Internet Archive/American Libraries",
    "material from the Google Print project",
    "*END THE SMALL PRINT",
    "***START OF THE PROJECT GUTENBERG",
    "This etext was produced by",
    "*** START OF THE COPYRIGHTED",
    "The Project Gutenberg",
    "http://gutenberg.spiegel.de/ erreichbar.",
    "Project Runeberg publishes",
    "Beginning of this Project Gutenberg",
    "Project Gutenberg Online Distributed",
    "Gutenberg Online Distributed",
    "the Project Gutenberg Online Distributed",
    "Project Gutenberg TEI",
    "This eBook was prepared by",
    "http://gutenberg2000.de erreichbar.",
    "This Etext was prepared by",
    "This Project Gutenberg Etext was prepared by",
    "Gutenberg Distributed Proofreaders",
    "Project Gutenberg Distributed Proofreaders",
    "the Project Gutenberg Online Distributed Proofreading Team",
    "**The Project Gutenberg",
    "*SMALL PRINT!",
    "More information about this book is at the top of this file.",
    "tells you about restrictions in how the file may be used.",
    "l'authorization à les utilizer pour preparer ce texte.",
    "of the etext through OCR.",
    "*****These eBooks Were Prepared By Thousands of Volunteers!*****",
    "We need your donations more than ever!",
    " *** START OF THIS PROJECT GUTENBERG",
    "****     SMALL PRINT!",
    '["Small Print" V.',
    '      (http://www.ibiblio.org/gutenberg/',
    'and the Project Gutenberg Online Distributed Proofreading Team',
    'Mary Meehan, and the Project Gutenberg Online Distributed Proofreading',
    '                this Project Gutenberg edition.',
))

TEXT_END_MARKERS = frozenset((
    "*** END OF THE PROJECT GUTENBERG",
    "*** END OF THIS PROJECT GUTENBERG",
    "***END OF THE PROJECT GUTENBERG",
    "End of the Project Gutenberg",
    "End of The Project Gutenberg",
    "Ende dieses Project Gutenberg",
    "by Project Gutenberg",
    "End of Project Gutenberg",
    "End of this Project Gutenberg",
    "Ende dieses Projekt Gutenberg",
    "        ***END OF THE PROJECT GUTENBERG",
    "*** END OF THE COPYRIGHTED",
    "End of this is COPYRIGHTED",
    "Ende dieses Etextes ",
    "Ende dieses Project Gutenber",
    "Ende diese Project Gutenberg",
    "**This is a COPYRIGHTED Project Gutenberg Etext, Details Above**",
    "Fin de Project Gutenberg",
    "The Project Gutenberg Etext of ",
    "Ce document fut presente en lecture",
    "Ce document fut présenté en lecture",
    "More information about this book is at the top of this file.",
    "We need your donations more than ever!",
    "END OF PROJECT GUTENBERG",
    " End of the Project Gutenberg",
    " *** END OF THIS PROJECT GUTENBERG",
))

LEGALESE_START_MARKERS = frozenset(("<<THIS ELECTRONIC VERSION OF",))
LEGALESE_END_MARKERS = frozenset(("SERVICE THAT CHARGES FOR DOWNLOAD",))


##
# adapted from https://github.com/c-w/Gutenberg/blob/master/gutenberg/acquire/text.py
def get_text_dir_from_index(index: int) -> str:
    return f"files/{index}"


##
# adapted from https://github.com/c-w/Gutenberg/blob/master/gutenberg/acquire/text.py
def _format_download_uri(index: int) -> str:
    """
    Returns the download location on the Project Gutenberg servers for a given text.

    Raises:
        UnknownDownloadUri: If no download location can be found for the text.
    """
    uri_root = r'https://www.gutenberg.org'
    extensions = ('.txt', '-8.txt', '-0.txt')
    path = get_text_dir_from_index(index)
    for extension in extensions:
        uri = '{root}/{path}/{etextno}{extension}'.format(
            root=uri_root,
            path=path,
            etextno=index,
            extension=extension)
        p = urlparse(uri)
        conn = http.client.HTTPSConnection(p.netloc)
        conn.request('HEAD', p.path)
        resp = conn.getresponse()
        if resp.status < 400:
            return uri
    raise UnknownDownloadUri("location not found for text at path: %s" % path)


##
# adapted from https://github.com/c-w/Gutenberg/blob/master/gutenberg/acquire/text.py
def get_text_by_id(index: int, return_bytes: bool = True) -> Union[str, bytes]:
    """
    Retrieve the text of a book from the Gutenberg project by its numerical ID.

    This function checks if the text is cached locally in a compressed format.
    If not, it downloads the text from the Project Gutenberg servers, detects its
    encoding, decodes it to a string, and stores it in a local cache for future use.

    Args:
        index (int): The unique Gutenberg ID of the book.
        return_bytes (bool, optional): If True, returns the text as bytes;
                                       otherwise, returns a string. Defaults to True.

    Returns:
        Union[str, bytes]: The full text of the book, either as a string or bytes,
        depending on the value of `return_bytes`.

    Raises:
        OSError: If there is an issue creating the cache directory.
        URLError: If downloading the text fails.
        UnicodeDecodeError: If the text encoding detection or decoding fails.
    """
    file_cache_location = os.path.join(GutenbergCacheSettings.TEXT_FILES_CACHE_FOLDER, str(index)+'.txt.gz')
    if not os.path.exists(file_cache_location):
        try:
            os.makedirs(os.path.dirname(file_cache_location))
        except OSError as ex:
            if ex.errno != errno.EEXIST:
                raise
        download_uri = _format_download_uri(index)

        text_bytes: bytes = urlopen(download_uri).read()
        encoding: str = chardet.detect(text_bytes)["encoding"]
        text: str = text_bytes.decode(encoding)

        with closing(gzip.open(file_cache_location, 'w')) as cache:
            cache.write(text.encode('utf-8'))

    with closing(gzip.open(file_cache_location, 'r')) as cache:
        text = cache.read().decode('utf-8')
    return text.encode('utf-8') if return_bytes else text


##
# this function is 100% from https://github.com/c-w/Gutenberg/blob/master/gutenberg/cleanup/strip_headers.py
def strip_headers(text: Union[str, bytes], return_bytes: bool = True) -> Union[str, bytes]:
    """
    Removes Project Gutenberg header and footer lines from the given text.

    This function attempts to strip out the standard header and footer markers
    used in Project Gutenberg texts, preserving only the main body of the work.
    It also removes legalese sections, such as licensing information, when detected.

    Args:
        text (Union[str, bytes]): The input text as a string or byte sequence.
        return_bytes (bool, optional): If True, returns the cleaned text as bytes;
                                       otherwise, returns a string. Defaults to True.

    Returns:
        Union[str, bytes]: The cleaned text with headers and footers removed.

    Notes:
        - The function identifies headers within the first 600 lines and footers after the first 100 lines.
        - It also removes legalese sections that start and end with predefined markers.
    """
    if isinstance(text, str):
        text = text.encode('utf-8')

    lines = text.splitlines()
    sep = os.linesep
    sep = sep.encode('utf-8')
    out = []
    i = 0
    footer_found = False
    ignore_section = False

    for line in lines:
        reset = False

        if i <= 600:
            # Check if the header ends here
            if any(line.startswith(token.encode('utf-8')) for token in TEXT_START_MARKERS):
                reset = True

            # If it's the end of the header, delete the output produced so far.
            # May be done several times, if multiple lines occur indicating the
            # end of the header
            if reset:
                out = []
                continue

        if i >= 100:
            # Check if the footer begins here
            if any(line.startswith(token.encode('utf-8')) for token in TEXT_END_MARKERS):
                footer_found = True

            # If it's the beginning of the footer, stop output
            if footer_found:
                break

        if any(line.startswith(token.encode('utf-8')) for token in LEGALESE_START_MARKERS):
            ignore_section = True
            continue
        elif any(line.startswith(token.encode('utf-8')) for token in LEGALESE_END_MARKERS):
            ignore_section = False
            continue

        if not ignore_section:
            stripline = line.rstrip(sep) 
            out.append(stripline)
            i += 1

    result = sep.join(out)
    return result if return_bytes else result.decode('utf-8')
