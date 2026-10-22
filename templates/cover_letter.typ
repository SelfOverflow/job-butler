// One-page cover letter matching resume.typ. Content arrives as JSON via
// `sys.inputs.data` and is rendered literally.
#let data = json(bytes(sys.inputs.data))

#set document(title: data.name + " - Cover Letter", author: data.name)
#set page(paper: "a4", margin: (x: 2.2cm, y: 2cm))
#set text(font: "New Computer Modern", size: 11pt, ligatures: false, lang: "en")
#set par(justify: false, leading: 0.65em, spacing: 1.1em)

#text(size: 15pt, weight: "bold", data.name) \
#text(size: 9pt, data.contact.join("  |  "))
#v(1.2em)
#data.date \
#data.company
#v(0.8em)

#data.greeting

#for paragraph in data.paragraphs [#paragraph

]

#data.closing \
#data.name
