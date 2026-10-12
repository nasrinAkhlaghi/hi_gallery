import { ArrowDownRight, ArrowUpRight, Flower2, Heart, Menu, Search } from "lucide-react";
import { BrowserRouter, Route, Routes, useParams } from "react-router-dom";
import { RoutePlaceholder, WorkspaceLayout } from "./components/RoutePlaceholder";

const categories = ["Ceramics", "Textiles", "Jewelry", "Home objects"];

function HomePage() {
  return (
    <main className="min-h-screen overflow-hidden bg-background text-foreground">
      <header className="mx-auto flex max-w-7xl items-center justify-between px-6 py-6 lg:px-12">
        <a href="#home" className="flex items-center gap-2 font-display text-xl font-semibold tracking-tight" aria-label="HI Gallery home">
          <span className="grid h-9 w-9 place-items-center rounded-full bg-primary text-sm text-primary-foreground">hi</span>
          <span>gallery</span>
        </a>
        <nav className="hidden items-center gap-9 text-sm text-muted-foreground md:flex" aria-label="Main navigation">
          <a className="transition hover:text-foreground" href="#discover">Discover</a>
          <a className="transition hover:text-foreground" href="#categories">Categories</a>
          <a className="transition hover:text-foreground" href="#about">Our story</a>
        </nav>
        <div className="flex items-center gap-3">
          <button className="grid h-10 w-10 place-items-center rounded-full border border-border" aria-label="Search"><Search size={17} /></button>
          <button className="hidden rounded-full bg-foreground px-5 py-2.5 text-sm text-background sm:block">Meet the makers</button>
          <button className="grid h-10 w-10 place-items-center md:hidden" aria-label="Open menu"><Menu size={20} /></button>
        </div>
      </header>

      <section id="home" className="mx-auto grid max-w-7xl items-center gap-12 px-6 pb-20 pt-10 lg:grid-cols-[1fr_0.9fr] lg:px-12 lg:pb-28 lg:pt-16">
        <div className="relative z-10">
          <p className="mb-6 flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.2em] text-primary"><Flower2 size={15} /> A marketplace for the made-by-hand</p>
          <h1 className="max-w-xl font-display text-5xl leading-[1.07] tracking-tight sm:text-6xl lg:text-7xl">Good things<br />have <span className="font-serif italic text-primary">human</span><br />hands behind them.</h1>
          <p className="mt-7 max-w-md text-base leading-7 text-muted-foreground">Meet independent makers and discover thoughtful pieces, made slowly and made to last.</p>
          <div className="mt-9 flex flex-wrap items-center gap-4">
            <a className="inline-flex items-center gap-3 rounded-full bg-primary px-6 py-3.5 text-sm font-medium text-primary-foreground transition hover:opacity-90" href="#discover">Explore the gallery <ArrowUpRight size={16} /></a>
            <span className="text-xs text-muted-foreground">A little more meaning in the everyday.</span>
          </div>
          <div className="mt-14 flex items-center gap-4 border-t border-border pt-6 text-xs text-muted-foreground"><span className="font-serif text-2xl italic text-foreground">01</span><span>Made by people, for people</span><ArrowDownRight size={15} className="ml-auto" /></div>
        </div>
        <div className="relative mx-auto w-full max-w-lg lg:max-w-none">
          <div className="aspect-[0.92] overflow-hidden rounded-[48%_48%_8px_8px] bg-[#d6b896]">
            <img className="h-full w-full object-cover" src="https://images.unsplash.com/photo-1578749556568-bc2c40e68b61?auto=format&fit=crop&w=1100&q=85" alt="Handmade ceramic vessels in warm natural light" />
          </div>
          <div className="absolute -bottom-5 left-0 rounded-2xl bg-white/95 p-4 shadow-xl shadow-stone-900/10 sm:-left-8 sm:p-5">
            <div className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-full bg-[#ece4d9] font-serif italic">M</span><div><p className="text-sm font-medium">Made with intention</p><p className="mt-1 text-xs text-muted-foreground">Every piece has a person behind it.</p></div><Heart className="ml-3 text-primary" size={17} /></div>
          </div>
          <span className="absolute right-0 top-8 rounded-full border border-white/70 bg-background/90 px-4 py-2 text-xs tracking-wide">Objects to keep</span>
        </div>
      </section>

      <section id="categories" className="border-y border-border bg-[#f1ede5]">
        <div className="mx-auto max-w-7xl px-6 py-12 lg:px-12 lg:py-16">
          <div className="mb-7 flex items-end justify-between"><div><p className="text-xs uppercase tracking-[0.18em] text-primary">Find your kind of handmade</p><h2 className="mt-2 font-display text-3xl tracking-tight">A world of good things</h2></div><a href="#discover" className="hidden text-sm underline underline-offset-4 sm:block">View all</a></div>
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">{categories.map((category, index) => <a key={category} href="#discover" className="group flex min-h-28 items-end justify-between rounded-2xl bg-background p-5 transition hover:-translate-y-1 hover:shadow-lg"><span><span className="mb-3 block text-xs text-muted-foreground">0{index + 1}</span><span className="font-display text-lg">{category}</span></span><ArrowUpRight size={17} className="text-muted-foreground transition group-hover:text-primary" /></a>)}</div>
        </div>
      </section>

      <section id="discover" className="mx-auto max-w-7xl px-6 py-20 text-center lg:px-12 lg:py-28">
        <p className="text-xs uppercase tracking-[0.18em] text-primary">The gallery is taking shape</p>
        <h2 className="mx-auto mt-4 max-w-2xl font-display text-3xl tracking-tight sm:text-4xl">A little space for makers, a lot of room for discovery.</h2>
        <p className="mx-auto mt-5 max-w-lg text-sm leading-6 text-muted-foreground">We’re getting everything ready. Soon you’ll find one-of-a-kind work and the people who make it here.</p>
      </section>
      <footer id="about" className="border-t border-border px-6 py-7 text-center text-xs text-muted-foreground">HI Gallery <span className="mx-2">·</span> Human Intelligence, made visible.</footer>
    </main>
  );
}

function ProductPlaceholder() {
  const { id } = useParams();
  return <RoutePlaceholder title="Product details" description={`Product ${id ?? ""}`} />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/browse" element={<RoutePlaceholder title="Browse" />} />
        <Route path="/products/:id" element={<ProductPlaceholder />} />
        <Route path="/cart" element={<RoutePlaceholder title="Cart" />} />
        <Route path="/checkout" element={<RoutePlaceholder title="Checkout" />} />
        <Route path="/orders" element={<RoutePlaceholder title="Orders" />} />
        <Route path="/seller" element={<WorkspaceLayout area="Seller Studio" />}>
          <Route index element={<RoutePlaceholder title="Dashboard" />} />
          <Route path="products" element={<RoutePlaceholder title="Products" />} />
          <Route path="orders" element={<RoutePlaceholder title="Orders" />} />
          <Route path="shop" element={<RoutePlaceholder title="Shop" />} />
          <Route path="settings" element={<RoutePlaceholder title="Settings" />} />
        </Route>
        <Route path="/admin" element={<WorkspaceLayout area="Admin Console" />}>
          <Route index element={<RoutePlaceholder title="Dashboard" />} />
          <Route path="sellers" element={<RoutePlaceholder title="Sellers" />} />
          <Route path="buyers" element={<RoutePlaceholder title="Buyers" />} />
          <Route path="products" element={<RoutePlaceholder title="Products" />} />
          <Route path="orders" element={<RoutePlaceholder title="Orders" />} />
          <Route path="reviews" element={<RoutePlaceholder title="Reviews" />} />
          <Route path="reports" element={<RoutePlaceholder title="Reports" />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
