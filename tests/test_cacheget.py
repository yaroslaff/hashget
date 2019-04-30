import hashget.cacheget
import hashget.file
import settings

def test_cg_get():
    """

    1. Clean URL from cache
    2. Download file. Check it's not cached
    3. Download again. Make sure it is cached.
    4. Check that hashsum of file is correct

    :return:
    """
    url = settings.package['url']
    size = settings.package['size']
    sha256 = settings.package['sha256']

    cg = hashget.cacheget.CacheGet()

    cg.clean_from_cache(url)
    r_uncached = cg.get(url)
    assert(r_uncached['downloaded'] == size)
    assert(r_uncached['cached'] == 0)

    f_uncached = hashget.file.File(r_uncached['file'])
    assert(f_uncached.hashes.hashsums['sha256'] == sha256)

    r_cached = cg.get(url)
    assert(r_cached['downloaded'] == 0)
    assert(r_cached['cached'] == size)

    f_cached = hashget.file.File(r_cached['file'])
    assert(f_cached.hashes.hashsums['sha256'] == sha256)