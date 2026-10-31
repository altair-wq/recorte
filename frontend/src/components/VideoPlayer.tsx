import { forwardRef } from 'react'

type Props = { src: string | null; poster?: string | null; onTime: (t: number) => void; onDuration?: (d: number) => void }

const VideoPlayer = forwardRef<HTMLVideoElement, Props>(function VideoPlayer({ src, poster, onTime, onDuration }, ref) {
  return (
    <div className="bg-black rounded-card overflow-hidden aspect-video">
      {src ? (
        <video ref={ref} src={src} poster={poster ?? undefined} controls className="w-full h-full"
          onTimeUpdate={(e) => onTime(e.currentTarget.currentTime)}
          onLoadedMetadata={(e) => onDuration?.(e.currentTarget.duration)} />
      ) : (
        <div className="w-full h-full grid place-items-center text-paper2 text-sm">…</div>
      )}
    </div>
  )
})

export default VideoPlayer
