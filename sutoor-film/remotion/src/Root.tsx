import { Composition } from "remotion";
import { edl } from "./edl";
import { Film } from "./Film";
import { Ember, reelDurationInFrames, reelFps } from "./Ember";
import { Journey, journeyDurationInFrames, journeyFps } from "./Journey";

export const RemotionRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="NisalScope"
        component={Film}
        durationInFrames={Math.round(edl.duration * edl.fps)}
        fps={edl.fps}
        width={1920}
        height={1080}
        defaultProps={{ layout: "scope" as const }}
      />
      <Composition
        id="NisalVertical"
        component={Film}
        durationInFrames={Math.round(edl.duration * edl.fps)}
        fps={edl.fps}
        width={1080}
        height={1920}
        defaultProps={{ layout: "vertical" as const }}
      />
      <Composition
        id="NisalEmber"
        component={Ember}
        durationInFrames={reelDurationInFrames("ember")}
        fps={reelFps("ember")}
        width={1080}
        height={1920}
        defaultProps={{ which: "ember" as const }}
      />
      <Composition
        id="NisalPaper"
        component={Ember}
        durationInFrames={reelDurationInFrames("paper")}
        fps={reelFps("paper")}
        width={1080}
        height={1920}
        defaultProps={{ which: "paper" as const }}
      />
      <Composition
        id="NisalJourney"
        component={Journey}
        durationInFrames={journeyDurationInFrames}
        fps={journeyFps}
        width={1080}
        height={1920}
      />
    </>
  );
};
