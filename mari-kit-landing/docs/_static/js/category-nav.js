document.addEventListener("DOMContentLoaded", () => {
  const categories = [
    ["start", "Getting started", [["overview", "Overview"], ["install", "Install"], ["architecture", "Architecture"]]],
    ["ingest", "Ingest & parse", [["documents", "Documents & ACLs"], ["connectors", "Polling & streaming connectors"], ["sync", "Synchronization"], ["parsers", "Knowledge parsers"], ["sections", "Sections & fact scans"], ["tags", "Tags & links"]]],
    ["retrieve", "Retrieve", [["retrieval", "Retrieval & indexes"], ["contradiction-retrieval", "Sparse contradiction retrieval"], ["retrieval-construction", "Retrieval construction"], ["adaptive-retrieval", "Adaptive retrieval"], ["context", "Context assembly"]]],
    ["govern", "Validate & govern", [["document-contradiction", "Document contradictions"], ["evidence", "Evidence contracts"], ["freshness", "Freshness & impact"], ["workflows", "Reviewed workflows"], ["verification", "Verification"], ["errors", "Errors & boundaries"]]],
    ["memory", "Organize memory", [["memory-algorithms", "Memory updates"], ["memory-organization", "Memory organization"], ["admission", "Admission"], ["consolidation", "Consolidation"]]],
    ["graph", "Graphs & projections", [["entity-resolution", "Entity resolution"], ["graph-processing", "Graph processing"], ["projections", "Projections"], ["graph", "Temporal graph"]]],
    ["agents", "Agents & procedures", [["trajectories", "Trajectories & agents"], ["procedural-learning", "Procedural learning"], ["procedures", "Procedural knowledge"]]],
    ["platform", "Platform & evaluation", [["artifacts", "Artifact model"], ["stores", "Storage protocols"], ["pipelines", "Pipelines"], ["memory-evaluation", "Memory evaluation"], ["compiler", "Evaluation compiler"]]],
  ];

  const menu = document.querySelector(".wy-menu-vertical");
  if (!menu) return;

  const sectionToCategory = new Map();
  for (const [key, , sections] of categories) {
    for (const [id] of sections) sectionToCategory.set(id, key);
  }

  menu.innerHTML = `
    <p class="caption" role="heading"><span class="caption-text">Topics</span></p>
    <div class="mari-major-nav">
      ${categories.map(([key, label]) => `<button type="button" data-category="${key}"><span>${label}</span><i>›</i></button>`).join("")}
    </div>
    <div class="mari-local-nav">
      <p>In this category</p>
      ${categories.map(([key, , sections]) => `<div data-subnav="${key}" hidden>${sections.map(([id, label]) => `<a href="#${id}">${label}</a>`).join("")}</div>`).join("")}
    </div>`;

  const buttons = [...menu.querySelectorAll("[data-category]")];
  const subnavs = [...menu.querySelectorAll("[data-subnav]")];
  const links = [...menu.querySelectorAll(".mari-local-nav a")];
  let activeCategory = "";

  function showCategory(key, scrollToFirst = false) {
    if (!categories.some(([candidate]) => candidate === key)) return;
    activeCategory = key;
    buttons.forEach((button) => {
      const active = button.dataset.category === key;
      button.classList.toggle("active", active);
      button.setAttribute("aria-expanded", String(active));
    });
    subnavs.forEach((nav) => { nav.hidden = nav.dataset.subnav !== key; });
    if (scrollToFirst) {
      const category = categories.find(([candidate]) => candidate === key);
      document.getElementById(category[2][0][0])?.scrollIntoView({behavior: "smooth"});
    }
  }

  function activateSection(id) {
    const category = sectionToCategory.get(id);
    if (category && category !== activeCategory) showCategory(category);
    links.forEach((link) => link.classList.toggle("active", link.hash === `#${id}`));
  }

  buttons.forEach((button) => button.addEventListener("click", () => showCategory(button.dataset.category, true)));
  links.forEach((link) => link.addEventListener("click", () => activateSection(link.hash.slice(1))));

  const trackedSections = [...sectionToCategory.keys()].map((id) => document.getElementById(id)).filter(Boolean);
  const observer = new IntersectionObserver((entries) => {
    const visible = entries.filter((entry) => entry.isIntersecting);
    if (!visible.length) return;
    visible.sort((left, right) => left.boundingClientRect.top - right.boundingClientRect.top);
    activateSection(visible[0].target.id);
  }, {rootMargin: "-8% 0px -78% 0px"});
  trackedSections.forEach((section) => observer.observe(section));

  const initialId = location.hash.slice(1);
  showCategory(sectionToCategory.get(initialId) || "start");
  activateSection(initialId || "overview");
  if (initialId && sectionToCategory.has(initialId)) {
    requestAnimationFrame(() => document.getElementById(initialId)?.scrollIntoView({behavior: "instant", block: "start"}));
  }
});
