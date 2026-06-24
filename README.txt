Harris Matrix Editor V10.1 STRAT

Beholder V10 CROWN-formatet: fase-linjer, justerbare konstruktionsbokse, lyse farver, PDF/PNG/SVG/Graph/HMCX.
Ny STRAT-layoutmotor:
- Relationer tolkes som source = yngre/over, target = ældre/under.
- Topsoil/top placeres altid øverst.
- Unexcavated placeres næstnederst.
- Natural/Geology placeres altid under Unexcavated.
- Direkte stratigrafiske relationer styrer lag-niveauer.
- Redundante top-/lange relationer fjernes kun for layout, så F1 ikke ender ved siden af Topsoil når F1 ligger under Topsoil.
- Barycentrisk branch-layout forsøger at placere børn under deres overliggende context og parallelle grene pænt ved siden af hinanden.
- Faser og strukturbokse kan flyttes/skaléres og gemmes i JSON/HMCX-project.xml annotations.

Workflow: .github/workflows/build-editor-v10-1.yml
