import { FixedSizeGrid as Grid, GridOnItemsRenderedProps } from "react-window";
import AutoSizer from "react-virtualized-auto-sizer";
import { Box, IconButton } from "@mui/material";
import CloudDownloadIcon from "@mui/icons-material/CloudDownload";
import type { SearchItem } from "../api/search";
import { withAccessToken } from "../api/client";

const TILE_WIDTH = 220;
const TILE_HEIGHT = 180;

export default function PhotoGrid({
  items,
  onEndReached,
  onSelect,
  onDownload,
}: {
  items: SearchItem[];
  onEndReached: () => void;
  onSelect: (item: SearchItem) => void;
  onDownload: (item: SearchItem) => void;
}) {
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
                <Box style={style} sx={{ p: 1 }}>
                  <Box
                    sx={{
                      position: "relative",
                      width: "100%",
                      height: "100%",
                      borderRadius: 2,
                      overflow: "hidden",
                      backgroundColor: "#e9edf5",
                    }}
                    onClick={() => onSelect(item)}
                  >
                    <img
                      src={withAccessToken(item.thumb_url)}
                      alt={item.keywords.join(", ")}
                      loading="lazy"
                      style={{ width: "100%", height: "100%", objectFit: "cover" }}
                    />
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
