type Lockable = {
  requestPointerLock: (options?: { unadjustedMovement?: boolean }) => Promise<void> | void;
};

function isUnsupported(error: unknown): boolean {
  return error instanceof TypeError || (error instanceof DOMException && error.name === 'NotSupportedError');
}

/**
 * Pointer lock with the OS mouse acceleration curve turned off.
 *
 * Without raw input, how far the view turns depends on how fast the mouse
 * moved, so a steady sweep speeds up and slows down under your hand.
 */
export async function requestRawPointerLock(element: Lockable): Promise<void> {
  try {
    await element.requestPointerLock({ unadjustedMovement: true });
  } catch (error) {
    // Only a capability error retries: re-requesting after a refusal trips
    // Chrome's guard against re-locking too soon after an exit.
    if (!isUnsupported(error)) return;
    await Promise.resolve(element.requestPointerLock()).catch(() => undefined);
  }
}
