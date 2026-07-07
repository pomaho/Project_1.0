import { FixedSizeGrid as Grid, GridOnItemsRenderedProps } from "react-window";
import AutoSizer from "react-virtualized-auto-sizer";
import { Box, IconButton } from "@mui/material";
import CloudDownloadIcon from "@mui/icons-material/CloudDownload";
import type { SearchItem } from "../api/search";
import { withAccessToken } from "../api/client";
import { useEffect, useRef, useState } from "react";

const TILE_WIDTH = 220;
const TILE_HEIGHT = 180;
const MAX_PARALLEL_IMAGE_LOADS = 6;

let activeImageLoads = 0;
const queuedImageLoads: Array<() => void> = [];

function releaseImageLoad() {
  activeImageLoads = Math.max(0, activeImageLoads - 1);
  const next = queuedImageLoads.shift();
  if (next) {
    activeImageLoads += 1;
    next();
  }
}

function scheduleImageLoad(start: (release: () => void) => void) {
  let cancelled = false;
  const run = () => {
    if (cancelled) {
      releaseImageLoad();
      return;
    }
    start(releaseImageLoad);
  };

  if (activeImageLoads < MAX_PARALLEL_IMAGE_LOADS) {
    activeImageLoads += 1;
    run();
  } else {
    queuedImageLoads.push(run);
  }

  return () => {
    cancelled = true;
    const index = queuedImageLoads.indexOf(run);
    if (index >= 0) {
      queuedImageLoads.splice(index, 1);
    }
  };
}

function PreviewImage({
  item,
  refreshToken,
  onRetry,
}: {
  item: SearchItem;
  refreshToken?: number;
  onRetry: () => void;
}) {
  const imageUrl = `${withAccessToken(item.thumb_url)}${refreshToken ? `&r=${refreshToken}` : ""}`;
  const [src, setSrc] = useState<string | null>(null);
  const releaseRef = useRef<(() => void) | null>(null);
  const releasedRef = useRef(true);

  const releaseOnce = () => {
    if (releasedRef.current) return;
    releasedRef.current = true;
    releaseRef.current?.();
    releaseRef.current = null;
  };

  useEffect(() => {
    setSrc(null);
    releaseRef.current = null;
    releasedRef.current = false;
    const cancel = scheduleImageLoad((release) => {
      releaseRef.current = release;
      setSrc(imageUrl);
    });
    return () => {
      cancel();
      releaseOnce();
    };
  }, [imageUrl]);

  if (!src) {
    return <Box sx={{ width: "100%", height: "100%", backgroundColor: "#101114" }} />;
  }

  return (
    <img
      src={src}
      alt={item.keywords.join(", ")}
      loading="lazy"
      style={{
        width: "100%",
        height: "100%",
        objectFit: "contain",
        backgroundColor: "#101114",
        cursor: "pointer",
      }}
      onLoad={releaseOnce}
      onError={() => {
        releaseOnce();
        window.setTimeout(onRetry, 2000);
      }}
    />
  );
}

export default function PhotoGrid({
  items,
  onEndReached,
  onSelect,
  onDownload,
  canDownload,
}: {
  items: SearchItem[];
  onEndReached: () => void;
  onSelect: (item: SearchItem) => void;
  onDownload: (item: SearchItem) => void;
  canDownload: boolean;
}) {
  const [refreshTokens, setRefreshTokens] = useState<Record<string, number>>({});

  return (
    <AutoSizer disableHeight={false}>
      {({ height, width }) => {
        const columnCount = Math.max(1, Math.floor(width / TILE_WIDTH));
        const rowCountLocal = Math.ceil(items.length / columnCount);

        return (
          <Grid
            columnCount={columnCount}
            columnWidth={TILE_WIDTH}
            height={height}
            rowCount={rowCountLocal}
            rowHeight={TILE_HEIGHT}
            width={width}
            onItemsRendered={({ visibleRowStopIndex }: GridOnItemsRenderedProps) => {
              if (visibleRowStopIndex >= Math.max(0, rowCountLocal - 2)) {
                onEndReached();
              }
            }}
          >
            {({ columnIndex, rowIndex, style }) => {
              const index = rowIndex * columnCount + columnIndex;
              const item = items[index];
              if (!item) {
                return <Box style={style} />;
              }
              return (
                <Box style={style} sx={{ p: 1, cursor: "pointer" }}>
                  <Box
                    sx={{
                      position: "relative",
                      width: "100%",
                      height: "100%",
                      borderRadius: 2,
                      overflow: "hidden",
                      backgroundColor: "#e9edf5",
                      cursor: "pointer",
                      transition: "transform 0.2s ease, box-shadow 0.2s ease",
                      "&:hover": {
                        transform: "translateY(-2px) scale(1.01)",
                        boxShadow: "0 10px 20px rgba(0,0,0,0.15)",
                      },
                    }}
                    onClick={() => onSelect(item)}
                  >
                    <PreviewImage
                      item={item}
                      refreshToken={refreshTokens[item.id]}
                      onRetry={() =>
                        setRefreshTokens((prev) => ({
                          ...prev,
                          [item.id]: Date.now(),
                        }))
                      }
                    />
                    {canDownload && (
                      <IconButton
                        size="small"
                        sx={{
                          position: "absolute",
                          bottom: 8,
                          right: 8,
                          backgroundColor: "rgba(255,255,255,0.85)",
                        }}
                        onClick={(event) => {
                          event.stopPropagation();
                          onDownload(item);
                        }}
                      >
                        <CloudDownloadIcon fontSize="small" />
                      </IconButton>
                    )}
                  </Box>
                </Box>
              );
            }}
          </Grid>
        );
      }}
    </AutoSizer>
  );
}
