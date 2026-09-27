"""Recorded URL policy. Preserve provenance; encode only at the request boundary.

Keep this policy and web/src/data/urls.ts covered by fixtures/url-cases.json.
No network requests or query parsing: signed query bytes must survive unchanged.
"""
import ipaddress
import re
import unicodedata
from urllib.parse import quote, urlsplit


def web_url(value, *, image=False):
    if not isinstance(value, str) or not value:
        return None
    if re.search(r'[\x00-\x1f\x7f\\]', value) or re.search(r'%(?![0-9a-fA-F]{2})', value):
        return None
    match = re.fullmatch(r'(https?)://([^/?#]+)(.*)', value, re.IGNORECASE)
    if not match or (image and match[1].lower() != 'https'):
        return None
    authority = match[2]
    if '@' in authority or '%' in authority:
        return None
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        if not host or parsed.port is not None and not 0 <= parsed.port <= 65535:
            return None
        if authority.endswith(':'):
            return None
        if ':' in host:
            ipaddress.IPv6Address(host)
            if not re.fullmatch(r'\[[0-9a-fA-F:.]+\](?::[0-9]+)?', authority):
                return None
        else:
            if any(c not in '.-_' and unicodedata.category(c)[0] not in 'LNM' for c in host):
                return None
            if any(not label for label in host.rstrip('.').split('.')):
                return None
            for label in host.rstrip('.').split('.'):
                if label.lower().startswith('xn--'):
                    label.encode('ascii').decode('idna')
                else:
                    label.encode('idna')
            # Avoid browser-specific shorthand/hex/octal IPv4 interpretations.
            last = host.rstrip('.').rsplit('.', 1)[-1]
            if re.fullmatch(r'[0-9]+|0x[0-9a-f]+', last, re.IGNORECASE):
                ipaddress.IPv4Address(host)
        # Keep authority as recorded (the browser handles IDN); don't serialize
        # parsed components, which would drop empty delimiters or rewrite queries.
        return value[:match.start(3)] + quote(match[3], safe="!$&'()*+,-./:;=?@_~%#[]")
    except (ValueError, UnicodeError):
        return None


def local_media_locator(value):
    return (isinstance(value, str) and bool(value)
            and not value.startswith(' ')
            and not re.search(r'[\x00-\x1f\x7f\\]', value)
            and not value.startswith('//')
            and not re.match(r'^[a-z][a-z0-9+.-]*:', value, re.IGNORECASE)
            and '..' not in value.split('/'))


def url_diagnostics(package):
    result = []
    for index, source in enumerate(package.get('sources', [])):
        if 'url' in source and web_url(source['url']) is None:
            result.append({'code': 'UNUSABLE_SOURCE_URL', 'path': f'/sources/{index}/url',
                           'message': 'Recorded source URL is not a usable HTTP(S) address; link omitted, record retained'})
    for index, media in enumerate(package.get('media', [])):
        if media.get('kind') == 'image' and not (web_url(media['locator'], image=True)
                                                or local_media_locator(media['locator'])):
            result.append({'code': 'UNUSABLE_MEDIA_LOCATOR', 'path': f'/media/{index}/locator',
                           'message': 'Image locator needs HTTPS or a safe local path; image omitted, record retained'})
    return result
