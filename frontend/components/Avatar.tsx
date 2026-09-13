'use client';

/** The roster head: an agent's colour and two eyes, at any size.
 *
 * Not a stage critter. The town it used to walk around is gone; this is
 * the identity chip that still appears beside a name. */
export function CritterAvatar({
  color,
  size = 34,
  alive = true,
  className,
}: {
  color: string;
  size?: number;
  alive?: boolean;
  className?: string;
}) {
  const eyeTop = size * 0.32;
  const eyeOff = size * 0.26;
  return (
    <div
      className={className}
      style={{
        position: 'relative',
        width: size,
        height: size,
        borderRadius: '50% 50% 45% 45% / 60% 60% 40% 40%',
        background: color,
        boxShadow: 'inset 0 -3px 0 rgba(0,0,0,0.08)',
        opacity: alive ? 1 : 0.5,
        filter: alive ? undefined : 'grayscale(0.8)',
        flexShrink: 0,
      }}
    >
      <span
        style={{
          position: 'absolute',
          left: eyeOff,
          top: eyeTop,
          width: size * 0.12,
          height: size * 0.16,
          borderRadius: '50%',
          background: '#2C2218',
        }}
      />
      <span
        style={{
          position: 'absolute',
          right: eyeOff,
          top: eyeTop,
          width: size * 0.12,
          height: size * 0.16,
          borderRadius: '50%',
          background: '#2C2218',
        }}
      />
    </div>
  );
}
