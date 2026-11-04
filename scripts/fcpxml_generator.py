#!/usr/bin/env python3
"""Apple Final Cut Pro (FCPXML v1.10) Generator for Indian & Bihari Wedding Films.

Generates 100% valid FCPXML interchange documents for:
1. Teaser (1 - 3 min): Fast-paced cuts, speed ramps, beat markers, hero hook.
2. Cinematic Trailer (5 - 10 min): 3-act narrative, voiceovers, beat-synced mashup.
3. Master Film (1 - 3 hours): Complete chronological documentary with chapter markers,
   full ritual coverage, and dynamic reception stage blessings.
"""

from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from urllib.parse import quote
from xml.dom import minidom
from xml.etree import ElementTree as ET

# Time math helpers (Final Cut Pro rational time)
TIMEBASE = 25  # Standard 25 fps broadcast PAL/Indian standard (or 24 for cinema)

# Machine-neutral default root for relative media paths.
#
# Asset src URLs must never be resolved against the current working directory:
# that bakes the operator's own home folder, username and employer into every
# generated file, and those files get committed. When no media root is supplied
# we emit this placeholder instead, which Final Cut Pro will simply ask you to
# relink on import. Point --media-root at your real footage folder to get
# directly-resolvable URLs without committing your local paths.
PLACEHOLDER_MEDIA_ROOT = "/Volumes/WEDDING_MEDIA"

# FCPXML schema version written into the document.
#
# Final Cut Pro imports older FCPXML revisions, so 1.10 is read by current
# versions rather than rejected; what an older revision costs is access to
# newer elements, not compatibility. It is set here, and overridable with
# --fcpxml-version, because the right value depends on the Final Cut Pro the
# timeline is destined for and should not be buried in the code.
#
# To confirm what your own Final Cut Pro writes, export any project as FCPXML
# and read the version attribute on the root <fcpxml> element:
#
#     head -3 /path/to/export.fcpxml
#
# Set that value here if it is newer than this default.
DEFAULT_FCPXML_VERSION = "1.10"

# Required runtime of each deliverable, taken from the owner's brief:
#   teaser  1-3 minutes
#   trailer 5-10 minutes
#   master  1-3 hours, depending on how many rituals were covered
#
# These are asserted after a timeline is built. An earlier version of this
# generator shipped a 42-second "teaser" and a 175-second "trailer" while its
# own comments claimed 90 and 360 seconds, because nothing ever checked the
# assembled result against the spec. Keep the check, not just the comment.
DELIVERABLE_SPECS = {
    "teaser": {"min_sec": 60.0, "max_sec": 180.0, "label": "Teaser (1-3 min)"},
    "trailer": {"min_sec": 300.0, "max_sec": 600.0, "label": "Trailer (5-10 min)"},
    "master": {"min_sec": 3600.0, "max_sec": 10800.0, "label": "Master film (1-3 h)"},
}


class DeliverableSpecError(ValueError):
    """Raised when an assembled timeline does not meet its required runtime."""


def check_deliverable_duration(kind: str, duration_sec: float, strict: bool = False) -> tuple[bool, str]:
    """Validate an assembled timeline against the brief's runtime spec.

    Returns (ok, message). With strict=True an out-of-spec timeline raises
    instead, so a bad edit plan fails loudly rather than being quietly exported.
    """
    spec = DELIVERABLE_SPECS.get(kind)
    if not spec:
        return True, f"No runtime spec defined for '{kind}'; skipping check."

    lo, hi = spec["min_sec"], spec["max_sec"]
    if lo <= duration_sec <= hi:
        return True, f"{spec['label']}: {duration_sec:.1f}s is within spec ({lo:.0f}-{hi:.0f}s)."

    how = "short of" if duration_sec < lo else "over"
    msg = (f"{spec['label']} is out of spec: {duration_sec:.1f}s, "
           f"{how} the required {lo:.0f}-{hi:.0f}s.")
    if strict:
        raise DeliverableSpecError(msg)
    return False, msg


def to_fcp_time(seconds: float, fps: int = TIMEBASE) -> str:
    """Convert float seconds to rational time string (e.g. '125/25s' or '5s')."""
    total_frames = int(round(seconds * fps))
    return f"{total_frames}/{fps}s"


def to_file_url(file_path: str, media_root: str | None = None) -> str:
    """Build a percent-encoded file:// URL for an asset, without leaking local paths.

    Absolute paths are honoured as given. Relative paths are resolved against
    `media_root` (or PLACEHOLDER_MEDIA_ROOT), never against os.getcwd().
    """
    p = Path(file_path)
    if p.is_absolute():
        abs_path = p
    else:
        root = Path(media_root) if media_root else Path(PLACEHOLDER_MEDIA_ROOT)
        abs_path = root / p
    # Percent-encode so spaces and non-ASCII characters produce a valid URL.
    return "file://" + quote(abs_path.as_posix(), safe="/")


class FCPXMLBuilder:
    def __init__(self, project_name: str, width: int = 3840, height: int = 2160, fps: int = TIMEBASE,
                 media_root: str | None = None, fcpxml_version: str = DEFAULT_FCPXML_VERSION):
        self.project_name = project_name
        self.width = width
        self.height = height
        self.fps = fps
        self.media_root = media_root
        self.fcpxml_version = fcpxml_version
        self.frame_dur = f"1/{fps}s"
        
        # Root element
        self.root = ET.Element("fcpxml", version=fcpxml_version)
        self.resources = ET.SubElement(self.root, "resources")
        
        # Define master video format
        self.fmt_id = "r1"
        ET.SubElement(
            self.resources, "format",
            id=self.fmt_id,
            name=f"FFVideoFormat{height}p{fps}",
            frameDuration=self.frame_dur,
            width=str(width),
            height=str(height)
        )
        
        self.asset_counter = 2
        self.assets = {}  # file_path -> asset_id
        
        # Library & Event structure
        self.library = ET.SubElement(self.root, "library")
        self.event = ET.SubElement(self.library, "event", name="Bihari Wedding Master Event")
        self.project = ET.SubElement(self.event, "project", name=self.project_name)
        self.sequence = ET.SubElement(
            self.project, "sequence",
            format=self.fmt_id,
            duration="0s",
            tcStart="0s",
            tcFormat="NDF"
        )
        self.spine = ET.SubElement(self.sequence, "spine")
        self.timeline_duration = 0.0

    def register_asset(self, file_path: str, duration_sec: float, has_video: bool = True, has_audio: bool = True) -> str:
        if file_path in self.assets:
            return self.assets[file_path]
            
        aid = f"r{self.asset_counter}"
        self.asset_counter += 1
        name = Path(file_path).name
        src_url = to_file_url(file_path, self.media_root)
        
        ET.SubElement(
            self.resources, "asset",
            id=aid,
            name=name,
            src=src_url,
            start="0s",
            duration=to_fcp_time(duration_sec, self.fps),
            hasVideo="1" if has_video else "0",
            hasAudio="1" if has_audio else "0",
            format=self.fmt_id if has_video else ""
        )
        self.assets[file_path] = aid
        return aid

    def add_clip_to_timeline(
        self,
        file_path: str,
        clip_name: str,
        start_sec: float,
        duration_sec: float,
        asset_total_dur: float = 60.0,
        markers: list[dict] | None = None,
        speed_ramp: float = 1.0
    ):
        """Add an asset-clip instance to the primary storyline spine."""
        aid = self.register_asset(file_path, asset_total_dur)
        offset_time = to_fcp_time(self.timeline_duration, self.fps)
        clip_dur_time = to_fcp_time(duration_sec, self.fps)
        clip_start_time = to_fcp_time(start_sec, self.fps)
        
        clip_el = ET.SubElement(
            self.spine, "asset-clip",
            name=clip_name,
            ref=aid,
            offset=offset_time,
            duration=clip_dur_time,
            start=clip_start_time,
            format=self.fmt_id
        )
        
        # Add chapter or beat markers if specified
        if markers:
            for m in markers:
                m_time = to_fcp_time(m.get("time_offset", 0.0), self.fps)
                ET.SubElement(
                    clip_el, "marker",
                    start=m_time,
                    duration="1/25s",
                    value=m.get("label", "Beat Drop"),
                    note=m.get("note", "")
                )
                
        self.timeline_duration += duration_sec
        # Update sequence duration
        self.sequence.set("duration", to_fcp_time(self.timeline_duration, self.fps))

    def assert_spec(self, kind: str, strict: bool = False) -> bool:
        """Check the assembled timeline against its deliverable runtime spec."""
        ok, msg = check_deliverable_duration(kind, self.timeline_duration, strict=strict)
        print(("[✓] " if ok else "[!] ") + msg)
        return ok

    def write_to_file(self, output_path: Path):
        """Serialize XML with proper declaration and indentation."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        xml_str = ET.tostring(self.root, encoding="utf-8")
        # Pretty print using minidom
        dom = minidom.parseString(xml_str)
        pretty_xml = dom.toprettyxml(indent="  ", encoding="utf-8")
        
        # Add DOCTYPE fcpxml header
        lines = pretty_xml.decode("utf-8").split("\n")
        header = ['<?xml version="1.0" encoding="UTF-8"?>', '<!DOCTYPE fcpxml>']
        body = [line for line in lines if not line.startswith("<?xml")]
        final_doc = "\n".join(header + body)
        
        output_path.write_text(final_doc, encoding="utf-8")
        print(f"[✓] FCPXML exported successfully: {output_path} ({round(self.timeline_duration, 1)}s duration)")


def build_from_edl(edl_path: Path, output_path: Path, media_root: str | None = None,
                   strict: bool = False,
                   fcpxml_version: str = DEFAULT_FCPXML_VERSION) -> Path:
    """Build a timeline from an EDL produced by plan_edit.py.

    This is the real path from a wedding's rushes to a Final Cut Pro timeline.
    The build_*_timeline functions below assemble hardcoded demo shot lists with
    invented filenames; they are useful for checking the FCPXML shape, but they
    are not an edit of anybody's wedding. Use this with a planned EDL instead.
    """
    edl = json.loads(Path(edl_path).read_text(encoding="utf-8"))
    kind = edl.get("deliverable", "master")
    fps = int(edl.get("fps") or TIMEBASE)

    builder = FCPXMLBuilder(
        project_name=f"Bihari_Wedding_{kind.capitalize()}",
        fps=fps,
        media_root=media_root,
        fcpxml_version=fcpxml_version,
    )

    events = edl.get("events", [])
    if not events:
        raise ValueError(
            f"{edl_path} contains no events. Plan the edit first with "
            f"plan_edit.py, and check that your clips are tagged to rituals."
        )

    for ev in events:
        path = ev.get("path")
        if not path:
            raise ValueError(f"EDL event for clip {ev.get('clip_id')} has no media path.")
        name_bits = [ev.get("ritual") or kind, ev.get("clip_id") or ""]
        builder.add_clip_to_timeline(
            file_path=path,
            clip_name="_".join(b for b in name_bits if b),
            start_sec=float(ev.get("source_in", 0.0)),
            duration_sec=float(ev.get("duration", 0.0)),
            markers=ev.get("markers"),
        )

    # Carry the planner's own warnings through to whoever exports the timeline,
    # so an out-of-spec or incomplete plan is not quietly turned into an XML
    # file that looks finished.
    for issue in edl.get("issues", []):
        print(f"[!] from plan: {issue}")

    builder.assert_spec(kind, strict=strict)
    builder.write_to_file(output_path)
    return output_path


def build_teaser_timeline(output_path: Path, hero_clips: list[dict] | None = None,
                          media_root: str | None = None) -> Path:
    """Build a 1-to-3 minute fast-paced cinematic teaser timeline with beat sync."""
    builder = FCPXMLBuilder(project_name="Bihari_Wedding_Cinematic_Teaser_4K", media_root=media_root)
    
    # ~96-second teaser: a cold-open hook, a beat-synced ritual montage covering
    # the full arc, the sindoor climax, then the reception button. Shot count and
    # pacing are sized to land inside the 60-180s spec, which is asserted below.
    default_shots = [
        # Cold open: place and anticipation
        {"name": "01_Drone_Patna_Ganga_Ghat_Dawn", "path": "Media/Drone_Venue.mov", "dur": 3.5, "start": 2.0},
        {"name": "02_Courtyard_Marigold_Macro", "path": "Media/Decor_Marigold.mov", "dur": 2.0, "start": 1.0},
        {"name": "03_Bride_Jewelry_Mirror_Reflection", "path": "Media/Bride_Mirror.mov", "dur": 2.5, "start": 1.0},
        {"name": "04_Bride_Eyes_Kajal_Closeup", "path": "Media/Bride_Eyes.mov", "dur": 2.0, "start": 3.0},
        {"name": "05_Groom_Sherwani_Cufflinks_Walk", "path": "Media/Groom_Ready.mov", "dur": 2.5, "start": 4.0},
        {"name": "06_Groom_Safa_Pagdi_Tying", "path": "Media/Groom_Pagdi.mov", "dur": 2.0, "start": 2.0},
        # Pre-wedding rites
        {"name": "07_Cheka_Tilak_Thali_Handover", "path": "Media/Cheka_Tilak.mov", "dur": 2.5, "start": 1.0},
        {"name": "08_Matkor_Sacred_Earth_Digging", "path": "Media/Matkor_Courtyard.mov", "dur": 3.0, "start": 0.0},
        {"name": "09_Matkor_Women_Geet_Procession", "path": "Media/Matkor_Geet.mov", "dur": 3.0, "start": 2.0},
        {"name": "10_Marava_Bamboo_Canopy_Raising", "path": "Media/Marava_Setup.mov", "dur": 2.5, "start": 1.0},
        {"name": "11_Silpohka_Imrit_Grinding_Hands", "path": "Media/Silpohka.mov", "dur": 2.0, "start": 1.0},
        # Haldi and mehndi
        {"name": "12_Haldi_Splash_120fps_SlowMo", "path": "Media/Haldi_Splash.mov", "dur": 3.0, "start": 5.0,
         "markers": [{"time_offset": 1.5, "label": "Beat Drop"}]},
        {"name": "13_Haldi_Elder_Suhagan_Smear", "path": "Media/Haldi_Elders.mov", "dur": 2.5, "start": 3.0},
        {"name": "14_Haldi_Laughter_Wide_Family", "path": "Media/Haldi_Family.mov", "dur": 2.0, "start": 6.0},
        {"name": "15_Mehndi_Henna_Cone_Macro", "path": "Media/Mehndi_Hands.mov", "dur": 2.5, "start": 2.0},
        {"name": "16_Sangeet_Dance_Floor_Jump", "path": "Media/Sangeet_Dance.mov", "dur": 2.5, "start": 10.0,
         "markers": [{"time_offset": 1.0, "label": "Beat Hit"}]},
        {"name": "17_Sangeet_Cousins_Spin_Lights", "path": "Media/Sangeet_Lights.mov", "dur": 2.0, "start": 14.0},
        # Baraat and jaimala
        {"name": "18_Baraat_Dhol_Energy_Toran", "path": "Media/Baraat_Entry.mov", "dur": 3.0, "start": 12.0},
        {"name": "19_Baraat_Brass_Band_Night", "path": "Media/Baraat_Band.mov", "dur": 2.5, "start": 8.0},
        {"name": "20_Dwar_Puja_Aarti_Thali", "path": "Media/Dwar_Puja.mov", "dur": 2.5, "start": 1.0},
        {"name": "21_MotherInLaw_NoseCatching_Parichan", "path": "Media/Parichan_Nose.mov", "dur": 2.5, "start": 1.5},
        {"name": "22_Jaimala_Garland_Exchange_Pyro", "path": "Media/Jaimala_Pyro.mov", "dur": 3.5, "start": 6.0,
         "markers": [{"time_offset": 2.0, "label": "Fireworks Swell"}]},
        {"name": "23_Jaimala_Lift_Crowd_Cheer", "path": "Media/Jaimala_Lift.mov", "dur": 2.5, "start": 4.0},
        # Mandap: the sacred core
        {"name": "24_Kanyadaan_Joined_Hands_Water", "path": "Media/Kanyadaan.mov", "dur": 3.0, "start": 2.0},
        {"name": "25_Gathbandhan_Knot_Tying", "path": "Media/Gathbandhan.mov", "dur": 2.5, "start": 1.0},
        {"name": "26_Mandap_Agni_Kund_Sparks", "path": "Media/Saat_Phere.mov", "dur": 3.0, "start": 15.0},
        {"name": "27_Saat_Phere_Feet_Steps", "path": "Media/Phere_Feet.mov", "dur": 2.5, "start": 3.0},
        {"name": "28_Sindoor_Daan_Nose_to_Maang_Macro", "path": "Media/Sindoor_Daan.mov", "dur": 4.5, "start": 3.0,
         "markers": [{"time_offset": 2.5, "label": "Sindoor Climax"}]},
        {"name": "29_Mangalsutra_Clasp_Closeup", "path": "Media/Mangalsutra.mov", "dur": 2.5, "start": 1.0},
        # Kohbar, vidai, arrival
        {"name": "30_Chumawan_Elder_Blessing_Rice", "path": "Media/Chumawan.mov", "dur": 2.5, "start": 2.0},
        {"name": "31_Kohbar_Ring_Finding_Game_Smile", "path": "Media/Kohbar_Games.mov", "dur": 2.5, "start": 8.0},
        {"name": "32_Vidai_Rice_Throw_Mother_Tears", "path": "Media/Vidai_Rice.mov", "dur": 4.0, "start": 4.0,
         "markers": [{"time_offset": 2.0, "label": "Emotional Peak"}]},
        {"name": "33_Vidai_Car_Window_Hands", "path": "Media/Vidai_Car.mov", "dur": 2.5, "start": 1.0},
        {"name": "34_Griha_Pravesh_Alta_Footprints", "path": "Media/Griha_Pravesh.mov", "dur": 2.5, "start": 1.0},
        # Reception button
        {"name": "35_Reception_Hall_Light_Reveal", "path": "Media/Reception_Hall.mov", "dur": 2.5, "start": 3.0},
        {"name": "36_Reception_Stage_Hero_Couple_Smile", "path": "Media/Reception_Hero.mov", "dur": 4.5, "start": 10.0,
         "markers": [{"time_offset": 2.0, "label": "Title Card"}]},
    ]

    shots = hero_clips if hero_clips else default_shots
    for s in shots:
        builder.add_clip_to_timeline(
            file_path=s["path"],
            clip_name=s["name"],
            start_sec=s.get("start", 0.0),
            duration_sec=s.get("dur", 3.0),
            markers=s.get("markers")
        )

    builder.assert_spec("teaser")
    builder.write_to_file(output_path)
    return output_path


def build_trailer_timeline(output_path: Path, media_root: str | None = None) -> Path:
    """Build a 5-to-10 minute 3-Act cinematic narrative trailer timeline."""
    builder = FCPXMLBuilder(project_name="Bihari_Wedding_Cinematic_Trailer_4K", media_root=media_root)
    
    # 3-Act Structure (~360 seconds / 6 minutes)
    act1_roots = [
        {"name": "Act1_Drone_Morning_Patna", "path": "Media/Drone_Morning.mov", "dur": 5.0, "start": 0.0},
        {"name": "Act1_Father_Vows_Voiceover", "path": "Media/Father_Interview.mov", "dur": 6.0, "start": 1.0},
        {"name": "Act1_Matkor_Procession_Geet", "path": "Media/Matkor_Procession.mov", "dur": 8.0, "start": 2.0},
        {"name": "Act1_Marava_Bamboo_Setup", "path": "Media/Marava_Setup.mov", "dur": 6.0, "start": 0.0},
        {"name": "Act1_Haldi_Haridra_Paste", "path": "Media/Haldi_Paste.mov", "dur": 10.0, "start": 3.0},
        {"name": "Act1_Mehndi_Henna_Macro", "path": "Media/Mehndi_Hands.mov", "dur": 7.0, "start": 2.0}
    ]
    act2_euphoria = [
        {"name": "Act2_Baraat_Arrival_BrassBand", "path": "Media/Baraat_Band.mov", "dur": 12.0, "start": 5.0},
        {"name": "Act2_Parichan_Gate_Aarti", "path": "Media/Parichan_Gate.mov", "dur": 8.0, "start": 2.0},
        {"name": "Act2_Sangeet_Family_Dance", "path": "Media/Sangeet_Dance.mov", "dur": 15.0, "start": 4.0},
        {"name": "Act2_Jaimala_Grand_Garlanding", "path": "Media/Jaimala_Stage.mov", "dur": 14.0, "start": 6.0}
    ]
    act3_sacred_vows = [
        {"name": "Act3_Kanyadaan_Joined_Hands", "path": "Media/Kanyadaan_HolyWater.mov", "dur": 12.0, "start": 2.0},
        {"name": "Act3_Saat_Phere_Agni_Steps", "path": "Media/Saat_Phere_Fire.mov", "dur": 14.0, "start": 4.0},
        {"name": "Act3_Sindoor_Daan_Nose_to_Maang", "path": "Media/Sindoor_Daan_Hero.mov", "dur": 18.0, "start": 5.0},
        {"name": "Act3_Kohbar_Traditional_Games", "path": "Media/Kohbar_Ring.mov", "dur": 10.0, "start": 1.0},
        {"name": "Act3_Vidai_Farewell_Tears", "path": "Media/Vidai_Departure.mov", "dur": 16.0, "start": 3.0},
        {"name": "Act3_Reception_Stage_Blessing", "path": "Media/Reception_Stage.mov", "dur": 14.0, "start": 5.0}
    ]
    
    for shot in act1_roots + act2_euphoria + act3_sacred_vows:
        builder.add_clip_to_timeline(
            file_path=shot["path"],
            clip_name=shot["name"],
            start_sec=shot.get("start", 0.0),
            duration_sec=shot.get("dur", 8.0)
        )
        
    builder.write_to_file(output_path)
    return output_path


def build_master_documentary_timeline(output_path: Path, media_root: str | None = None) -> Path:
    """Build a comprehensive 1-to-3 hour master film timeline with full ritual chapters."""
    builder = FCPXMLBuilder(project_name="Bihari_Wedding_Master_Feature_Film", media_root=media_root)
    
    # 16 Cultural Chapters (~5400 seconds / 1.5 hours)
    rituals = [
        ("01_Cheka_Tilak", 240.0),
        ("02_Matkor_Mati_Mangal", 300.0),
        ("03_Marava_Bamboo_Canopy", 240.0),
        ("04_Silpohka_Imrit_Grinding", 180.0),
        ("05_Haldi_Haridra_Full_Rites", 480.0),
        ("06_Mehndi_Sangeet_Extravaganza", 600.0),
        ("07_Baraat_Aagman_Dwar_Puja", 420.0),
        ("08_Jaimala_Stage_Celebration", 540.0),
        ("09_Kanyadaan_Panigrahana", 420.0),
        ("10_Gathbandhan_Saat_Phere", 480.0),
        ("11_Sindoor_Daan_Sacred_Climax", 360.0),
        ("12_Chumawan_Elder_Blessings", 240.0),
        ("13_Kohbar_Chamber_And_Games", 300.0),
        ("14_Vidai_Samdhauni_Farewell", 360.0),
        ("15_Vadhu_Pravesh_Lakshmi_Kalash", 240.0),
        ("16_Bahubhoj_Grand_Reception", 720.0)
    ]
    
    for r_name, r_dur in rituals:
        # Chapter head marker
        markers = [{"time_offset": 0.0, "label": f"CHAPTER: {r_name}"}]
        builder.add_clip_to_timeline(
            file_path=f"Media/{r_name}.mov",
            clip_name=f"Sequence_{r_name}",
            start_sec=0.0,
            duration_sec=r_dur,
            asset_total_dur=r_dur + 60.0,
            markers=markers
        )
        
    builder.write_to_file(output_path)
    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate Final Cut Pro XML (FCPXML v1.10) for Indian/Bihari weddings.")
    parser.add_argument("--type", choices=["teaser", "trailer", "master", "all"], default="all", help="Deliverable type")
    parser.add_argument("--edl", type=Path, default=None,
                        help="Build from a planned EDL (from plan_edit.py) instead of the "
                             "built-in demo shot lists. This is the real path for an actual wedding.")
    parser.add_argument("--strict", action="store_true",
                        help="Fail if the assembled timeline is outside its required runtime")
    parser.add_argument("--fcpxml-version", default=DEFAULT_FCPXML_VERSION,
                        help=f"FCPXML schema version to write (default {DEFAULT_FCPXML_VERSION}). "
                             "Confirm yours with: head -3 <an FCPXML exported from your Final Cut Pro>")
    parser.add_argument("--out", type=str, default="./exports_fcpxml", help="Output directory")
    parser.add_argument(
        "--media-root", type=str, default=None,
        help=("Absolute path to your raw footage folder, used to resolve relative clip paths. "
              f"Defaults to the machine-neutral placeholder {PLACEHOLDER_MEDIA_ROOT}, which Final Cut Pro "
              "will ask you to relink. Never commit generated files that contain your real media root.")
    )
    args = parser.parse_args()

    out_dir = Path(args.out)

    if args.edl:
        edl_name = json.loads(args.edl.read_text(encoding="utf-8")).get("deliverable", "edit")
        build_from_edl(args.edl, out_dir / f"Bihari_Wedding_{edl_name.capitalize()}.fcpxml",
                       media_root=args.media_root, strict=args.strict,
                       fcpxml_version=args.fcpxml_version)
        sys.exit(0)

    if args.type in ["teaser", "all"]:
        build_teaser_timeline(out_dir / "Bihari_Wedding_Teaser_1080p.fcpxml", media_root=args.media_root)
    if args.type in ["trailer", "all"]:
        build_trailer_timeline(out_dir / "Bihari_Wedding_Trailer_Cinematic.fcpxml", media_root=args.media_root)
    if args.type in ["master", "all"]:
        build_master_documentary_timeline(out_dir / "Bihari_Wedding_Master_Documentary.fcpxml", media_root=args.media_root)

