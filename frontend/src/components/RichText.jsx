// Renders Gemini's light markdown (paragraphs, "- " bullets, "1." lists, **bold**)
// as React elements. Never uses innerHTML, so model output can't inject markup.

function inline(text, keyBase) {
  return String(text)
    .split(/(\*\*[^*]+\*\*)/g)
    .map((part, i) =>
      part.length > 4 && part.startsWith("**") && part.endsWith("**") ? (
        <strong key={keyBase + i}>{part.slice(2, -2)}</strong>
      ) : (
        part
      )
    );
}

export default function RichText({ text }) {
  const blocks = [];
  let list = null;
  const flush = () => {
    if (list) blocks.push(list);
    list = null;
  };

  String(text || "")
    .replace(/\r/g, "")
    .split("\n")
    .forEach((raw) => {
      const line = raw.trimEnd();
      const bullet = line.match(/^\s*[-*•]\s+(.*)$/);
      const numbered = line.match(/^\s*\d+[.)]\s+(.*)$/);
      if (bullet || numbered) {
        const type = bullet ? "ul" : "ol";
        if (!list || list.type !== type) {
          flush();
          list = { type, items: [] };
        }
        list.items.push((bullet || numbered)[1]);
        return;
      }
      flush();
      if (!line.trim()) return;
      const heading = line.match(/^#{1,6}\s+(.*)$/);
      blocks.push({ type: "p", text: heading ? `**${heading[1]}**` : line });
    });
  flush();

  return (
    <div className="rich">
      {blocks.map((b, i) => {
        if (b.type === "p") return <p key={i}>{inline(b.text, `${i}-`)}</p>;
        const Tag = b.type;
        return (
          <Tag key={i}>
            {b.items.map((item, j) => (
              <li key={j}>{inline(item, `${i}-${j}-`)}</li>
            ))}
          </Tag>
        );
      })}
    </div>
  );
}
