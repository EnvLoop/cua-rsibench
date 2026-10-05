"""Pure public frame validation; provider and training code are absent."""
from dataclasses import dataclass,asdict
import hashlib,json,io,warnings

def digest(value):
    encoded = value if isinstance(value, bytes) else json.dumps(value, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(encoded).hexdigest()

class ProxyError(ValueError):
    """Only a fixed subtype is safe to expose, never an exception body."""
    def __init__(self, subtype):
        self.subtype = subtype
        super().__init__(subtype)

@dataclass(frozen=True)
class Limits:
    image_bytes: int = 8_000_000
    image_pixels: int = 4_194_304
    image_side: int = 4096
    instruction_bytes: int = 16_384
    visible_text_bytes: int = 65_536
    input_tokens: int = 32_768
    output_tokens: int = 512
    decoded_output_bytes: int = 65_536
    max_actions: int = 90
    request_timeout_seconds: int = 240

    def __post_init__(self):
        for name, value in asdict(self).items():
            if type(value) is not int or value <= 0:
                raise ProxyError('invalid_limits')
        if (self.image_bytes > 32_000_000 or self.image_pixels > 16_777_216 or self.image_side > 8192
                or self.instruction_bytes > 262_144 or self.visible_text_bytes > 1_048_576
                or self.input_tokens + self.output_tokens > 64_000 or self.output_tokens > 4096
                or self.decoded_output_bytes > 1_048_576 or self.max_actions > 1000
                or self.request_timeout_seconds > 900):
            raise ProxyError('invalid_limits')

    @property
    def http_body_bytes(self):
        # JSON can escape text to six bytes per character; the independent text
        # and image limits are checked again after parsing.
        return ((self.image_bytes + 2) // 3) * 4 + 6 * (self.instruction_bytes + self.visible_text_bytes) + 4096

def image_from_bytes(data, limits):
    from PIL import Image, UnidentifiedImageError
    if not isinstance(data, bytes) or not data or len(data) > limits.image_bytes:
        raise ProxyError('invalid_image_bytes')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as opened:
                if opened.format not in ('PNG', 'JPEG') or getattr(opened, 'n_frames', 1) != 1:
                    raise ProxyError('unsupported_image_format')
                width, height = opened.size
                if not 0 < width <= limits.image_side or not 0 < height <= limits.image_side or width * height > limits.image_pixels:
                    raise ProxyError('image_pixel_limit')
                format_name = opened.format.lower()
                opened.verify()
            with Image.open(io.BytesIO(data)) as opened:
                opened.load()
                image = opened.convert('RGB')
                image.info.clear()  # Do not forward embedded EXIF/metadata.
    except ProxyError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise ProxyError('invalid_image_encoding') from None
    return image, {'format': format_name, 'width': width, 'height': height,
                   'bytes': len(data), 'pixels': width * height, 'sha256': digest(data)}
