import { describe, expect, it, vi } from 'vitest';
import { requestRawPointerLock } from '@/lib/pointerLock';

describe('requestRawPointerLock', () => {
  it('asks for unaccelerated mouse input', async () => {
    const request = vi.fn().mockResolvedValue(undefined);
    await requestRawPointerLock({ requestPointerLock: request });

    expect(request).toHaveBeenCalledTimes(1);
    expect(request).toHaveBeenCalledWith({ unadjustedMovement: true });
  });

  it('falls back to a plain lock where raw input is refused', async () => {
    const request = vi
      .fn()
      .mockRejectedValueOnce(new DOMException('no raw input', 'NotSupportedError'))
      .mockResolvedValueOnce(undefined);
    await requestRawPointerLock({ requestPointerLock: request });

    expect(request).toHaveBeenLastCalledWith();
    expect(request).toHaveBeenCalledTimes(2);
  });

  it('falls back when the browser throws instead of rejecting', async () => {
    const request = vi
      .fn()
      .mockImplementationOnce(() => {
        throw new TypeError('options not supported');
      })
      .mockReturnValueOnce(undefined);
    await requestRawPointerLock({ requestPointerLock: request });

    expect(request).toHaveBeenLastCalledWith();
  });

  it('does not retry when the lock simply is not granted', async () => {
    // A second request straight after a refused one is what trips Chrome's
    // "exited the lock too recently" guard, so only a capability error retries.
    const request = vi.fn().mockRejectedValue(new DOMException('denied', 'SecurityError'));
    await requestRawPointerLock({ requestPointerLock: request });

    expect(request).toHaveBeenCalledTimes(1);
  });
});
