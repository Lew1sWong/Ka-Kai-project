"use client";

import { useRouter } from "next/navigation";
import SharedMirrorQuantApp from "./MirrorQuantAppClient.jsx";

type MirrorQuantAppProps = {
  initialView?: "landing" | "workspace";
};

export default function MirrorQuantApp({
  initialView = "landing",
}: MirrorQuantAppProps) {
  const router = useRouter();
  const enterPlatform = initialView === "landing"
    ? () => router.push("/workspace")
    : null;
  const showLanding = initialView === "workspace"
    ? () => router.push("/")
    : null;

  return (
    <SharedMirrorQuantApp
      initialView={initialView}
      onEnterPlatform={enterPlatform}
      onShowLanding={showLanding}
    />
  );
}
