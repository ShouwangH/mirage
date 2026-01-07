/**
 * Simple HTML5 video player component.
 */

import styles from './VideoPlayer.module.css';

interface VideoPlayerProps {
  src: string;
  poster?: string;
}

export function VideoPlayer({ src, poster }: VideoPlayerProps) {
  return (
    <div className={styles.container}>
      <video
        className={styles.video}
        src={src}
        poster={poster}
        controls
        preload="metadata"
      >
        Your browser does not support the video tag.
      </video>
    </div>
  );
}
