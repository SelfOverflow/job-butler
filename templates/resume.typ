// ATS-friendly single-column resume. All content arrives as JSON via
// `sys.inputs.data` (never spliced into markup), so profile text is rendered
// literally. Built-in font keeps output identical locally and in Docker;
// ligatures are off so text extraction never yields glyph substitutions.
#let data = json(bytes(sys.inputs.data))

#set document(title: data.name + " - Resume", author: data.name)
#set page(paper: "a4", margin: (x: 1.5cm, y: 1.3cm))
#set text(font: "New Computer Modern", size: 10pt, ligatures: false, lang: "en")
#set par(justify: false, leading: 0.55em)
#set list(indent: 0.4em, body-indent: 0.5em, spacing: 0.45em)

#show heading.where(level: 2): it => block(above: 0.9em, below: 0.5em, width: 100%)[
  #text(size: 11pt, weight: "bold", it.body)
  #v(-0.7em)
  #line(length: 100%, stroke: 0.5pt)
]

#align(center)[
  #text(size: 17pt, weight: "bold", data.name) \
  #v(-0.2em)
  #text(size: 9pt, data.contact.join("  |  "))
]

#if data.summary != "" [
  == Summary
  #data.summary
]

#if data.skills.len() > 0 [
  == Technical Skills
  #for group in data.skills [*#group.label:* #group.names.join(", ") \ ]
]

== Professional Experience
#for role in data.roles [
  #block(above: 0.7em, below: 0.35em)[
    *#role.title*, #role.company #h(1fr) #role.dates \
    #text(size: 9pt, style: "italic", role.location)
  ]
  #for bullet in role.bullets [- #bullet]
]

#if data.education.len() > 0 [
  == Education
  #for entry in data.education [#entry \ ]
]

#if data.certifications.len() > 0 [
  == #data.certifications_heading
  #for cert in data.certifications [- #cert]
]
