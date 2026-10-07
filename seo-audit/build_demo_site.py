"""Builds 'Brightwater Physio', a fictional clinic site with realistic SEO problems planted on purpose.
The planted problems are listed in PLANTED so the crawler's results can be checked against them."""

import json
import pathlib
import random

from PIL import Image, ImageDraw

ROOT = pathlib.Path(__file__).parent / "demo_site"
COPY = json.loads((pathlib.Path(__file__).parent / "copy.json").read_text(encoding="utf-8"))

PLANTED = {
    "title_too_long": ["/"],
    "missing_meta_description": ["/", "/sports-injury.html"],
    "multiple_h1": ["/"],
    "heavy_image": ["/"],
    "image_missing_alt": ["/", "/about.html"],
    "duplicate_title": ["/services.html", "/about.html"],
    "duplicate_meta_description": ["/services.html", "/about.html"],
    "canonical_points_elsewhere": ["/services.html"],
    "thin_content": ["/sports-injury.html"],
    "broken_image": ["/sports-injury.html"],
    "broken_internal_url": ["/team.html", "/old-offers.html"],
    "missing_h1": ["/contact.html"],
    "missing_viewport": ["/contact.html"],
    "missing_lang": ["/contact.html"],
    "blocked_by_robots_txt": ["/blog/desk-stretches.html", "/blog/"],
    "indexable_page_missing_from_sitemap": ["/blog/desk-stretches.html"],
    "orphan_page": ["/pricing.html"],
    "noindex_page_in_sitemap": ["/pricing.html"],
    "sitemap_lists_broken_url": ["/old-offers.html"],
}

CSS = """body{font-family:system-ui,sans-serif;margin:0;color:#1f2d3a;line-height:1.6}
header{background:#0e5e6f;color:#fff;padding:14px 24px;display:flex;justify-content:space-between;flex-wrap:wrap;gap:12px}
header a{color:#fff;margin-right:16px;text-decoration:none}main{max-width:820px;margin:0 auto;padding:24px 16px}
img{max-width:100%;height:auto}footer{background:#eef4f5;padding:20px 24px;font-size:14px;margin-top:40px}
.btn{background:#0e5e6f;color:#fff;padding:10px 18px;display:inline-block;text-decoration:none;border-radius:4px}"""

NAV = """<header><strong>Brightwater Physio</strong><nav><a href="/">Home</a><a href="/services.html">Services</a>
<a href="/back-pain.html">Back pain</a><a href="/sports-injury.html">Sports injuries</a><a href="/about.html">About</a>
<a href="/blog/">Blog</a><a href="/contact.html">Contact</a></nav></header>"""
FOOT = """<footer>Brightwater Physio (fictional clinic for an SEO audit sample) · 14 Harbour Road, Bristol · 0117 000 0000</footer>"""


def paras(key):
    return "".join(f"<p>{p.strip()}</p>" for p in COPY[key].split("\n\n") if p.strip())


def page(path, title, body, desc=None, canonical=None, lang=True, viewport=True, robots=None):
    head = ['<meta charset="utf-8">']
    if viewport:
        head.append('<meta name="viewport" content="width=device-width, initial-scale=1">')
    head.append(f"<title>{title}</title>")
    if desc:
        head.append(f'<meta name="description" content="{desc}">')
    if robots:
        head.append(f'<meta name="robots" content="{robots}">')
    canon = canonical or ("https://www.brightwaterphysio.example" + path.replace("index.html", ""))
    head.append(f'<link rel="canonical" href="{canon.replace("https://www.brightwaterphysio.example", "")}">')
    html = (f'<!doctype html><html{" lang=\"en-GB\"" if lang else ""}><head>{"".join(head)}<style>{CSS}</style></head>'
            f"<body>{NAV}<main>{body}</main>{FOOT}</body></html>")
    out = ROOT / path.lstrip("/")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")


def make_images():
    img_dir = ROOT / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    random.seed(7)
    # Deliberately heavy hero: uncompressed PNG with photographic-style noise
    hero = Image.new("RGB", (1800, 900))
    px = hero.load()
    for y in range(900):
        for x in range(1800):
            n = random.randint(-18, 18)
            px[x, y] = (14 + y // 12 + n, 94 + x // 40 + n, 111 + n)
    hero.save(img_dir / "clinic-hero.png")
    for name, colour in (("treatment-room.jpg", (200, 225, 228)), ("team.jpg", (220, 230, 210))):
        im = Image.new("RGB", (800, 500), colour)
        ImageDraw.Draw(im).text((30, 30), name, fill=(40, 60, 70))
        im.save(img_dir / name, quality=75)


def build():
    make_images()
    page("/index.html",
         "Brightwater Physio | Physiotherapy, Sports Massage and Rehab Clinic in Bristol, UK - Book Today",
         f'<h1>Physiotherapy in Bristol</h1><img src="/img/clinic-hero.png" width="1800" height="900">'
         f'<h1>Welcome to Brightwater</h1>{paras("home")}<p><a class="btn" href="/contact.html">Book an appointment</a></p>')
    shared_desc = "Brightwater Physio is a friendly physiotherapy clinic in Bristol offering treatment for pain and injuries."
    page("/services.html", "Brightwater Physio",
         f"<h1>Our services</h1>{paras('services')}",
         desc=shared_desc, canonical="https://www.brightwaterphysio.example/")
    page("/back-pain.html", "Lower Back Pain Physiotherapy in Bristol | Brightwater Physio",
         f'<h1>Lower back pain treatment</h1><img src="/img/treatment-room.jpg" alt="Treatment room with a physiotherapy couch" width="800" height="500">'
         f"{paras('back_pain')}",
         desc="Lower back pain? Our chartered physiotherapists in Bristol assess the cause and build a treatment plan around you. Book online.")
    page("/sports-injury.html", "Sports Injury Clinic Bristol | Brightwater Physio",
         '<h1>Sports injuries</h1><img src="/img/knee-taping.jpg" alt="Knee taping for a runner">'
         "<p>We treat sprains, strains and overuse injuries for runners, footballers and gym-goers. "
         "Our physiotherapists assess the injury, explain what is going on and give you a clear plan to get back to training.</p>"
         '<p><a class="btn" href="/contact.html">Book a sports injury assessment</a></p>')
    page("/about.html", "Brightwater Physio",
         f'<h1>About Brightwater Physio</h1><img src="/img/team.jpg" width="800" height="500">{paras("about")}'
         '<p>Meet <a href="/team.html">our team of physiotherapists</a>.</p>',
         desc=shared_desc)
    page("/contact.html", "Contact Brightwater Physio | Book a Physiotherapy Appointment",
         "<h2>Get in touch</h2><p>Call us on 0117 000 0000 or email hello@brightwaterphysio.example. "
         "We are open Monday to Friday 8am to 7pm and Saturday 9am to 1pm. The clinic is a five-minute walk from Temple Meads station, "
         "with step-free access and two parking spaces for patients.</p><p>New patients can usually be seen within three working days.</p>",
         desc="Contact Brightwater Physio in Bristol to book a physiotherapy appointment. Open weekdays until 7pm and Saturday mornings.",
         lang=False, viewport=False)
    page("/blog/index.html", "Physiotherapy Tips and Advice | Brightwater Physio Blog",
         '<h1>Blog</h1><p>Practical advice from our physiotherapists.</p>'
         '<ul><li><a href="/blog/desk-stretches.html">5 desk stretches for office workers</a></li></ul>',
         desc="Practical physiotherapy tips and exercise advice from the chartered physiotherapists at Brightwater Physio in Bristol.")
    page("/blog/desk-stretches.html", "5 Desk Stretches for Office Workers | Brightwater Physio",
         f"<h1>5 desk stretches for office workers</h1>{paras('blog_desk')}",
         desc="Five simple desk stretches from a Bristol physiotherapist to ease neck, shoulder and back stiffness during the working day.")
    page("/pricing.html", "Physiotherapy Prices | Brightwater Physio",
         "<h1>Prices</h1><p>Initial assessment (45 minutes): £60. Follow-up treatment (30 minutes): £48. "
         "Sports massage (45 minutes): £50. Ergonomic workplace assessment: from £120. We accept most major health insurers; "
         "please bring your authorisation code to your first appointment. Cancellations with less than 24 hours' notice are charged in full. "
         "Payment by card or contactless at the end of each session. Block bookings of five follow-up sessions are discounted to £220 when paid in advance. "
         "Prices last reviewed in 2026. If you are unsure which appointment you need, call reception and we will help you choose.</p>",
         desc="Clear physiotherapy prices at Brightwater Physio in Bristol: assessments, follow-ups, sports massage and workplace assessments.",
         robots="noindex")
    (ROOT / "robots.txt").write_text("User-agent: *\nDisallow: /blog/\n\nSitemap: /sitemap.xml\n", encoding="utf-8")
    base = "http://localhost:8766"
    urls = ["/", "/services.html", "/back-pain.html", "/sports-injury.html", "/about.html", "/contact.html",
            "/blog/", "/pricing.html", "/old-offers.html"]
    (ROOT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{base}{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (pathlib.Path(__file__).parent / "planted_issues.json").write_text(json.dumps(PLANTED, indent=2), encoding="utf-8")
    print("built", sum(1 for _ in ROOT.rglob("*.html")), "pages")


if __name__ == "__main__":
    build()
