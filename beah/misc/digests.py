import hashlib

__DIGEST_BY_LEN = {32:'md5', 40:'sha1', 64:'sha256', 128:'sha512'}


def which_digest(digest):
    """
    Return digest method used to create digest.

    This is at the moment detrermined by the length of digest.
    """
    if digest:
        return __DIGEST_BY_LEN.get(len(digest), None)
    return None


def mk_digest(digest):
    """
    Create a (digest_method, digest) tuple.

    This returns a tuple or None. This method performs no checks. Use
    make_digest when some checks are expected.
    """
    if digest:
        dm = which_digest(digest)
        if dm:
            return (dm, digest)
    return None


def make_digest(digest):
    """
    Create a (digest_method, digest) tuple.

    This returns a tuple or None.
    """
    if digest:
        if isinstance(digest, (list, tuple)):
            if digest[1] and digest[0] == which_digest(digest[1]):
                return digest
            return None
        dm = which_digest(digest)
        if dm:
            return (dm, digest)
    return None


__DIGEST_CONSTRUCTOR = {'md5':hashlib.md5, 'sha1':hashlib.sha1, # pylint: disable=E1101
        'sha256':hashlib.sha256, 'sha512':hashlib.sha512}       # pylint: disable=E1101


class NoDigest(object):
    """
    This is a dummy Digest class producing empty digests.
    """
    digest_size = 0
    blocksize = 1
    def __init__(self, str=''): pass
    def update(self, str): return None
    def hexdigest(self): return ""
    def digest(self): return ""
    def copy(self): return self


def DigestConstructor(digest_method):
    """
    Return class used for calculating checksum using digest_method algorithm.

    This method uses non-standard name as it is only a class multiplexer.
    """
    return __DIGEST_CONSTRUCTOR.get(digest_method, NoDigest)

