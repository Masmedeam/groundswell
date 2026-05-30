// Server Component — reads Laurie's engine overview from data/laurie-engine/
// JSON at request time and passes to HomeShell. HomeShell carries the chat
// state and decides between the landing grid (messages.length === 0) and the
// existing chat workspace (messages.length > 0). The chat workspace itself is
// literally unchanged from the prior page.tsx — only the landing branch is
// new, and only this file became a server component.
import { getEngineOverview } from "@/lib/engine-overview";
import HomeShell from "@/components/HomeShell";

export default function Page() {
  const { overview, fetchedAt } = getEngineOverview();
  return <HomeShell overview={overview} fetchedAt={fetchedAt} />;
}
