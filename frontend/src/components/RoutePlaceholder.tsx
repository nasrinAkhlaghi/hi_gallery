import { Link, Outlet } from "react-router-dom";

type RoutePlaceholderProps = {
  title: string;
  description?: string;
};

export function RoutePlaceholder({ title, description }: RoutePlaceholderProps) {
  return (
    <main className="mx-auto min-h-screen max-w-5xl px-6 py-12 text-foreground">
      <Link to="/" className="text-sm text-primary">HI Gallery</Link>
      <p className="mt-16 text-xs uppercase tracking-[0.18em] text-muted-foreground">Page scaffold</p>
      <h1 className="mt-3 font-display text-4xl">{title}</h1>
      {description && <p className="mt-3 text-muted-foreground">{description}</p>}
      <p className="mt-4 text-sm text-muted-foreground">This page is a route placeholder.</p>
    </main>
  );
}

const sellerLinks = ["", "products", "orders", "shop", "settings"];
const adminLinks = ["", "sellers", "buyers", "products", "orders", "reviews", "reports"];

export function WorkspaceLayout({ area }: { area: "Seller Studio" | "Admin Console" }) {
  const basePath = area === "Seller Studio" ? "/seller" : "/admin";
  const links = area === "Seller Studio" ? sellerLinks : adminLinks;

  return (
    <div className="min-h-screen bg-[#f8f5ef] text-foreground">
      <header className="border-b border-border px-6 py-5">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4">
          <div><Link to="/" className="text-sm text-primary">HI Gallery</Link><h1 className="mt-1 font-display text-xl">{area}</h1></div>
          <nav aria-label={`${area} navigation`} className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
            {links.map((path) => {
              const label = path ? path[0].toUpperCase() + path.slice(1) : "Dashboard";
              return <Link key={path || "dashboard"} to={path ? `${basePath}/${path}` : basePath} className="text-muted-foreground hover:text-foreground">{label}</Link>;
            })}
          </nav>
        </div>
      </header>
      <Outlet />
    </div>
  );
}
