"use client";
// Persistent top navigation for the institutional surface.
//
// Pages render this themselves rather than going through app/layout.tsx,
// so the `right` slot can hold page-specific affordances:
//   - Landing  → <AskAnalystDock /> (the docked popover)
//   - Chat     → a "← Markets overview" button that calls resetChat()
//   - Pitch / Data Sources / Methodology → no right slot
//
// Logo + wordmark act as a home link to "/". Nav uses Next's usePathname
// to highlight the active route in ground green with a thin underline.
import Link from "next/link";
import Image from "next/image";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/",             label: "Market Overview" },
  { href: "/data-sources", label: "Data Sources" },
  { href: "/methodology",  label: "Methodology" },
  { href: "/pitch",        label: "Pitch" },
];

export default function TopNav({
  right,
  onLogoClick,
}: {
  right?: React.ReactNode;
  // When the chat workspace mounts this nav, clicking the logo should
  // ALSO call resetChat() (aborts the in-flight stream + clears
  // messages) on top of the route navigation. Other contexts pass
  // nothing and the logo is a plain Link.
  onLogoClick?: () => void;
}) {
  const pathname = usePathname() || "/";
  return (
    <div className="border-b border-rule bg-cream">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-6 px-8 py-3.5">
        {/* Left: logo + wordmark + nav */}
        <div className="flex items-center gap-8">
          {onLogoClick ? (
            <button
              type="button"
              onClick={onLogoClick}
              title="Back to market overview"
              className="flex items-center gap-2.5 transition hover:opacity-80"
            >
              <Image src="/logo.png" alt="HomeStar" width={28} height={28} priority />
              <span className="font-serif text-[17px] font-semibold leading-none text-ground-ink">
                Home<span className="text-ground">Star</span>
              </span>
            </button>
          ) : (
            <Link
              href="/"
              className="flex items-center gap-2.5 transition hover:opacity-80"
              title="Back to market overview"
            >
              <Image src="/logo.png" alt="HomeStar" width={28} height={28} priority />
              <span className="font-serif text-[17px] font-semibold leading-none text-ground-ink">
                Home<span className="text-ground">Star</span>
              </span>
            </Link>
          )}
          <nav className="flex items-center gap-6">
            {NAV.map((n) => {
              const active =
                n.href === "/"
                  ? pathname === "/"
                  : pathname === n.href || pathname.startsWith(`${n.href}/`);
              return (
                <Link
                  key={n.href}
                  href={n.href}
                  className={
                    "relative text-[10.5px] font-semibold uppercase tracking-[0.18em] transition " +
                    (active
                      ? "text-ground"
                      : "text-ink-soft hover:text-ground")
                  }
                >
                  {n.label}
                  {active && (
                    <span className="pointer-events-none absolute -bottom-[14px] left-0 right-0 h-[2px] bg-ground" />
                  )}
                </Link>
              );
            })}
          </nav>
        </div>

        {/* Right: optional page-specific slot */}
        {right ? <div className="flex items-center gap-5">{right}</div> : null}
      </div>
    </div>
  );
}
