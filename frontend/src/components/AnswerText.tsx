import { parseAnswer } from "../lib/citations";
import { cn } from "../lib/cn";

type Props = {
  text: string;
  onCite?: (marker: number) => void;
  activeMarker?: number | null;
};

/** Renders an answer, turning each [n] into a button that opens source n. */
export function AnswerText({ text, onCite, activeMarker = null }: Props) {
  return (
    <p className="whitespace-pre-wrap text-[15px] leading-relaxed">
      {parseAnswer(text).map((segment, index) =>
        segment.kind === "text" ? (
          <span key={index}>{segment.text}</span>
        ) : (
          <span key={index} className="mx-0.5 inline-flex gap-0.5 align-baseline">
            {segment.markers.map((marker) => (
              <button
                key={marker}
                type="button"
                aria-label={`Show source ${marker}`}
                onClick={() => onCite?.(marker)}
                className={cn(
                  "inline-flex h-5 min-w-5 items-center justify-center rounded-md px-1 text-xs font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-teal/40",
                  activeMarker === marker
                    ? "bg-teal text-white"
                    : "bg-teal-light text-teal hover:bg-teal hover:text-white",
                )}
              >
                {marker}
              </button>
            ))}
          </span>
        ),
      )}
    </p>
  );
}
