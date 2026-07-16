import os
from flask import Response, current_app, stream_with_context


def stream_file_safely(file_path, mimetype, chunk_size=1024 * 1024):
    """Stream a file in chunks to avoid server-level sendfile failures."""
    try:
        with open(file_path, 'rb') as probe:
            probe.read(1)
    except OSError as exc:
        current_app.logger.warning("[File Stream] Initial read failed for %s: %s", file_path, exc)
        raise

    def _iter_chunks():
        try:
            with open(file_path, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield chunk
        except OSError as exc:
            current_app.logger.warning("[File Stream] Mid-stream read failed for %s: %s", file_path, exc)

    res = Response(stream_with_context(_iter_chunks()), mimetype=mimetype)
    res.headers['Accept-Ranges'] = 'bytes'

    try:
        res.headers['Content-Length'] = str(os.path.getsize(file_path))
    except OSError:
        pass

    return res
