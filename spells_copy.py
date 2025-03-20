SPELL_SCHOOLS = [
    "Abjuration",
    "Conjuration",
    "Divination",
    "Enchantment",
    "Evocation",
    "Illusion",
    "Necromancy",
    "Transmutation"
]

SPELL_LEVELS = [
    "Cantrip",
    "1st",
    "2nd",
    "3rd",
    "4th",
    "5th",
    "6th",
    "7th",
    "8th",
    "9th"
]

# This is a sample of spells - you can expand this list
SPELLS_BY_LEVEL = {
    "Cantrip": [
        {
            "name": "Acid Splash",
            "school": "Conjuration",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, S",
            "duration": "Instantaneous",
            "description": "You hurl a bubble of acid. Choose one creature within range, or choose two creatures within range that are within 5 feet of each other. A target must succeed on a Dexterity saving throw or take 1d6 acid damage."
        },
        {
            "name": "Blade Ward",
            "school": "Abjuration",
            "casting_time": "1 action",
            "range": "Self",
            "components": "V, S",
            "duration": "1 round",
            "description": "You extend your hand and trace a sigil of warding in the air. Until the end of your next turn, you have resistance against bludgeoning, piercing, and slashing damage dealt by weapon attacks."
        },
        {
            "name": "Chill Touch",
            "school": "Necromancy",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S",
            "duration": "1 round",
            "description": "You create a ghostly, skeletal hand in the space of a creature within range. Make a ranged spell attack against the creature to assail it with the chill of the grave. On a hit, the target takes 1d8 necrotic damage, and it can't regain hit points until the start of your next turn."
        },
        {
            "name": "Dancing Lights",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S, M (a bit of phosphorus or wychwood, or a glowworm)",
            "duration": "Concentration, up to 1 minute",
            "description": "You create up to four torch-sized lights within range, making them appear as torches, lanterns, or glowing orbs that hover in the air for the duration."
        },
        {
            "name": "Fire Bolt",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S",
            "duration": "Instantaneous",
            "description": "You hurl a mote of fire at a creature or object within range. Make a ranged spell attack against the target. On a hit, the target takes 1d10 fire damage."
        },
        {
            "name": "Light",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "Touch",
            "components": "V, M (a firefly or phosphorescent moss)",
            "duration": "1 hour",
            "description": "You touch one object that is no larger than 10 feet in any dimension. Until the spell ends, the object sheds bright light in a 20-foot radius and dim light for an additional 20 feet."
        },
        {
            "name": "Mage Hand",
            "school": "Conjuration",
            "casting_time": "1 action",
            "range": "30 feet",
            "components": "V, S",
            "duration": "1 minute",
            "description": "A spectral, floating hand appears at a point you choose within range. The hand lasts for the duration or until you dismiss it as an action. The hand vanishes if it is ever more than 30 feet away from you or if you cast this spell again."
        },
        {
            "name": "Message",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S, M (a short piece of copper wire)",
            "duration": "1 round",
            "description": "You point your finger toward a creature within range and whisper a message. The target (and only the target) hears the message and can reply in a whisper that only you can hear."
        },
        {
            "name": "Minor Illusion",
            "school": "Illusion",
            "casting_time": "1 action",
            "range": "30 feet",
            "components": "S, M (a bit of fleece)",
            "duration": "1 minute",
            "description": "You create a sound or an image of an object within range that lasts for the duration. The illusion also ends if you dismiss it as an action or cast this spell again."
        },
        {
            "name": "Prestidigitation",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "10 feet",
            "components": "V, S",
            "duration": "Up to 1 hour",
            "description": "This spell is a minor magical trick that novice spellcasters use for practice. You create one of several minor magical effects within range."
        }
    ],
    "1st": [
        {
            "name": "Alarm",
            "school": "Abjuration",
            "casting_time": "1 minute",
            "range": "30 feet",
            "components": "V, S, M (a tiny bell and a piece of fine silver wire)",
            "duration": "8 hours",
            "description": "You set an alarm against unwanted intrusion. Choose a door, a window, or an area within range that is no larger than a 20-foot cube. Until the spell ends, an alarm alerts you whenever a tiny or larger creature touches or enters the warded area."
        },
        {
            "name": "Burning Hands",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "Self (15-foot cone)",
            "components": "V, S",
            "duration": "Instantaneous",
            "description": "As you hold your hands with thumbs touching and fingers spread, a thin sheet of flames shoots forth from your outstretched fingertips. Each creature in a 15-foot cone must make a Dexterity saving throw. A creature takes 3d6 fire damage on a failed save, or half as much damage on a successful one."
        },
        {
            "name": "Charm Person",
            "school": "Enchantment",
            "casting_time": "1 action",
            "range": "30 feet",
            "components": "V, S",
            "duration": "1 hour",
            "description": "You attempt to charm a humanoid you can see within range. It must make a Wisdom saving throw, and does so with advantage if you or your companions are fighting it. If it fails the saving throw, it is charmed by you until the spell ends or until you or your companions do anything harmful to it."
        },
        {
            "name": "Detect Magic",
            "school": "Divination",
            "casting_time": "1 action",
            "range": "Self",
            "components": "V, S",
            "duration": "Concentration, up to 10 minutes",
            "description": "For the duration, you sense the presence of magic within 30 feet of you. If you sense magic in this way, you can use your action to see a faint aura around any visible creature or object in the area that bears magic."
        },
        {
            "name": "Magic Missile",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S",
            "duration": "Instantaneous",
            "description": "You create three glowing darts of magical force. Each dart hits a creature of your choice that you can see within range. A dart deals 1d4 + 1 force damage to its target. The darts all strike simultaneously, and you can direct them to hit one creature or several."
        }
    ],
    "2nd": [
        {
            "name": "Acid Arrow",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "90 feet",
            "components": "V, S, M (powdered rhubarb leaf and an adder's stomach)",
            "duration": "Instantaneous",
            "description": "A shimmering green arrow streaks toward a target within range and bursts in a spray of acid. Make a ranged spell attack. On a hit, the target takes 4d4 acid damage immediately and 2d4 acid damage at the end of its next turn."
        },
        {
            "name": "Alter Self",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "Self",
            "components": "V, S",
            "duration": "Concentration, up to 1 hour",
            "description": "You assume a different form. When you cast the spell, choose one of the following options, the effects of which last for the duration of the spell: Aquatic Adaptation, Change Appearance, or Natural Weapons."
        },
        {
            "name": "Blindness/Deafness",
            "school": "Necromancy",
            "casting_time": "1 action",
            "range": "30 feet",
            "components": "V",
            "duration": "1 minute",
            "description": "You can blind or deafen a foe. Choose one creature that you can see within range to make a Constitution saving throw. If it fails, the target is either blinded or deafened (your choice) for the duration."
        },
        {
            "name": "Darkness",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, M (bat fur and a drop of pitch or piece of coal)",
            "duration": "Concentration, up to 10 minutes",
            "description": "Magical darkness spreads from a point you choose within range to fill a 15-foot-radius sphere for the duration. The darkness spreads around corners. A creature with darkvision can't see through this darkness, and nonmagical light can't illuminate it."
        },
        {
            "name": "Invisibility",
            "school": "Illusion",
            "casting_time": "1 action",
            "range": "Touch",
            "components": "V, S, M (an eyelash encased in gum arabic)",
            "duration": "Concentration, up to 1 hour",
            "description": "A creature you touch becomes invisible until the spell ends. Anything the target is wearing or carrying is invisible as long as it is on the target's person. The spell ends for a target that attacks or casts a spell."
        },
        {
            "name": "Mirror Image",
            "school": "Illusion",
            "casting_time": "1 action",
            "range": "Self",
            "components": "V, S",
            "duration": "1 minute",
            "description": "Three illusory duplicates of yourself appear in your space. Until the spell ends, the duplicates move with you and mimic your actions, shifting position so it's impossible to track which image is real."
        }
    ],
    "3rd": [
        {
            "name": "Animate Dead",
            "school": "Necromancy",
            "casting_time": "1 minute",
            "range": "10 feet",
            "components": "V, S, M (a drop of blood, a piece of flesh, and a pinch of bone dust)",
            "duration": "Instantaneous",
            "description": "This spell creates an undead servant. Choose a pile of bones or a corpse of a Medium or Small humanoid within range. Your spell imbues the target with a foul mimicry of life, raising it as an undead creature."
        },
        {
            "name": "Counterspell",
            "school": "Abjuration",
            "casting_time": "1 reaction",
            "range": "60 feet",
            "components": "S",
            "duration": "Instantaneous",
            "description": "You attempt to interrupt a creature in the process of casting a spell. If the creature is casting a spell of 3rd level or lower, its spell fails and has no effect. If it is casting a spell of 4th level or higher, make an ability check using your spellcasting ability."
        },
        {
            "name": "Fireball",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "150 feet",
            "components": "V, S, M (a tiny ball of bat guano and sulfur)",
            "duration": "Instantaneous",
            "description": "A bright streak flashes from your pointing finger to a point you choose within range and then blossoms with a low roar into an explosion of flame. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A target takes 8d6 fire damage on a failed save, or half as much damage on a successful one."
        },
        {
            "name": "Fly",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "Touch",
            "components": "V, S, M (a wing feather from any bird)",
            "duration": "Concentration, up to 10 minutes",
            "description": "You touch a willing creature. The target gains a flying speed of 60 feet for the duration. When the spell ends, the target falls if it is still aloft, unless it can stop the fall."
        },
        {
            "name": "Haste",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "30 feet",
            "components": "V, S, M (a shaving of licorice root)",
            "duration": "Concentration, up to 1 minute",
            "description": "Choose a willing creature that you can see within range. Until the spell ends, the target's speed is doubled, it gains a +2 bonus to AC, it has advantage on Dexterity saving throws, and it gains an additional action on each of its turns."
        },
        {
            "name": "Lightning Bolt",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "Self (100-foot line)",
            "components": "V, S, M (a bit of fur and a rod of amber, crystal, or glass)",
            "duration": "Instantaneous",
            "description": "A stroke of lightning forming a line 100 feet long and 5 feet wide blasts out from you in a direction you choose. Each creature in the line must make a Dexterity saving throw. A creature takes 8d6 lightning damage on a failed save, or half as much damage on a successful one."
        }
    ],
    "4th": [
        {
            "name": "Banishment",
            "school": "Abjuration",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, S, M (an item distasteful to the target)",
            "duration": "Concentration, up to 1 minute",
            "description": "You attempt to send one creature that you can see within range to another plane of existence. The target must succeed on a Charisma saving throw or be banished. If the target is native to the plane of existence you're on, you banish the target to a harmless demiplane. While there, the target is incapacitated. The target remains there until the spell ends, at which point the target reappears in the space it left or in the nearest unoccupied space if that space is occupied."
        },
        {
            "name": "Blight",
            "school": "Necromancy",
            "casting_time": "1 action",
            "range": "30 feet",
            "components": "V, S",
            "duration": "Instantaneous",
            "description": "Necromantic energy washes over a creature of your choice that you can see within range, draining moisture and vitality from it. The target must make a Constitution saving throw. The target takes 8d8 necrotic damage on a failed save, or half as much damage on a successful one. This spell has no effect on undead or constructs."
        },
        {
            "name": "Confusion",
            "school": "Enchantment",
            "casting_time": "1 action",
            "range": "90 feet",
            "components": "V, S, M (three nut shells)",
            "duration": "Concentration, up to 1 minute",
            "description": "This spell assaults and twists creatures' minds, spawning delusions and provoking uncontrolled actions. Each creature in a 10-foot-radius sphere centered on a point you choose within range must succeed on a Wisdom saving throw when you cast this spell or be affected by it."
        },
        {
            "name": "Dimension Door",
            "school": "Conjuration",
            "casting_time": "1 action",
            "range": "500 feet",
            "components": "V",
            "duration": "Instantaneous",
            "description": "You teleport yourself from your current location to any other spot within range. You arrive at exactly the spot desired. It can be a place you can see, one you can visualize, or one you can describe by stating distance and direction."
        },
        {
            "name": "Greater Invisibility",
            "school": "Illusion",
            "casting_time": "1 action",
            "range": "Touch",
            "components": "V, S",
            "duration": "Concentration, up to 1 minute",
            "description": "You or a creature you touch becomes invisible until the spell ends. Anything the target is wearing or carrying is invisible as long as it is on the target's person. Unlike regular invisibility, this spell remains active even when the target attacks or casts spells."
        },
        {
            "name": "Ice Storm",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "300 feet",
            "components": "V, S, M (a pinch of dust and a few drops of water)",
            "duration": "Instantaneous",
            "description": "A hail of rock-hard ice pounds to the ground in a 20-foot-radius, 40-foot-high cylinder centered on a point within range. Each creature in the cylinder must make a Dexterity saving throw. A creature takes 2d8 bludgeoning damage and 4d6 cold damage on a failed save, or half as much damage on a successful one."
        },
        {
            "name": "Polymorph",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, S, M (a caterpillar cocoon)",
            "duration": "Concentration, up to 1 hour",
            "description": "This spell transforms a creature that you can see within range into a new form. An unwilling creature must make a Wisdom saving throw to avoid the effect. The spell has no effect on a shapechanger or a creature with 0 hit points."
        },
        {
            "name": "Stone Shape",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "Touch",
            "components": "V, S, M (soft clay, which must be worked into roughly the desired shape of the stone object)",
            "duration": "Instantaneous",
            "description": "You touch a stone object of Medium size or smaller or a section of stone no more than 5 feet in any dimension and form it into any shape that suits your purpose. For example, you could shape a large rock into a weapon, idol, or coffer, or make a small passage through a wall, as long as the wall is less than 5 feet thick."
        },
        {
            "name": "Wall of Fire",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S, M (a small piece of phosphorus)",
            "duration": "Concentration, up to 1 minute",
            "description": "You create a wall of fire on a solid surface within range. You can make the wall up to 60 feet long, 20 feet high, and 1 foot thick, or a ringed wall up to 20 feet in diameter, 20 feet high, and 1 foot thick. The wall is opaque and lasts for the duration."
        }
    ],
    "5th": [
        {
            "name": "Animate Objects",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S",
            "duration": "Concentration, up to 1 minute",
            "description": "Objects come to life at your command. Choose up to ten nonmagical objects within range that are not being worn or carried. Medium targets count as two objects, Large targets count as four objects, Huge targets count as eight objects. You can animate objects no larger than Huge. Each target animates and becomes a creature under your control until the spell ends."
        },
        {
            "name": "Cloudkill",
            "school": "Conjuration",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S",
            "duration": "Concentration, up to 10 minutes",
            "description": "You create a 20-foot-radius sphere of poisonous, yellow-green fog centered on a point you choose within range. The fog spreads around corners. It lasts for the duration or until strong wind disperses the fog, ending the spell. Its area is heavily obscured. When a creature enters the spell's area for the first time on a turn or starts its turn there, that creature must make a Constitution saving throw. The creature takes 5d8 poison damage on a failed save, or half as much damage on a successful one."
        },
        {
            "name": "Cone of Cold",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "Self (60-foot cone)",
            "components": "V, S, M (a small crystal or glass cone)",
            "duration": "Instantaneous",
            "description": "A blast of cold air erupts from your hands. Each creature in a 60-foot cone must make a Constitution saving throw. A creature takes 8d8 cold damage on a failed save, or half as much damage on a successful one."
        },
        {
            "name": "Hold Monster",
            "school": "Enchantment",
            "casting_time": "1 action",
            "range": "90 feet",
            "components": "V, S, M (a small, straight piece of iron)",
            "duration": "Concentration, up to 1 minute",
            "description": "Choose a creature that you can see within range. The target must succeed on a Wisdom saving throw or be paralyzed for the duration. This spell has no effect on undead. At the end of each of its turns, the target can make another Wisdom saving throw. On a success, the spell ends on the target."
        },
        {
            "name": "Legend Lore",
            "school": "Divination",
            "casting_time": "10 minutes",
            "range": "Self",
            "components": "V, S, M (incense worth at least 250 gp, which the spell consumes, and four ivory strips worth at least 50 gp each)",
            "duration": "Instantaneous",
            "description": "Name or describe a person, place, or object. The spell brings to your mind a brief summary of the significant lore about the thing you named. The lore might consist of current tales, forgotten stories, or even secret lore that has never been widely known."
        },
        {
            "name": "Scrying",
            "school": "Divination",
            "casting_time": "10 minutes",
            "range": "Self",
            "components": "V, S, M (a focus worth at least 1,000 gp, such as a crystal ball, a silver mirror, or a font filled with holy water)",
            "duration": "Concentration, up to 10 minutes",
            "description": "You can see and hear a particular creature you choose that is on the same plane of existence as you. The target must make a Wisdom saving throw, which is modified by how well you know the target and the sort of physical connection you have to it."
        },
        {
            "name": "Wall of Force",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "120 feet",
            "components": "V, S, M (a pinch of powder made by crushing a clear gemstone)",
            "duration": "Concentration, up to 10 minutes",
            "description": "An invisible wall of force springs into existence at a point you choose within range. The wall appears in any orientation you choose, as a horizontal or vertical barrier or at an angle. The wall can be free floating or resting on a solid surface. You can form it into a hemispherical dome or a sphere with a radius of up to 10 feet."
        }
    ],
    "6th": [
        {
            "name": "Chain Lightning",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "150 feet",
            "components": "V, S, M (a bit of fur; a piece of amber, glass, or a crystal rod; and three silver pins)",
            "duration": "Instantaneous",
            "description": "You create a bolt of lightning that arcs toward a target of your choice that you can see within range. Three bolts then leap from that target to as many as three other targets, each of which must be within 30 feet of the first target. A target can be a creature or an object and can be targeted by only one of the bolts. A target must make a Dexterity saving throw. The target takes 10d8 lightning damage on a failed save, or half as much damage on a successful one."
        },
        {
            "name": "Disintegrate",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, S, M (a lodestone and a pinch of dust)",
            "duration": "Instantaneous",
            "description": "A thin green ray springs from your pointing finger to a target that you can see within range. The target can be a creature, an object, or a creation of magical force. A creature targeted by this spell must make a Dexterity saving throw. On a failed save, the target takes 10d6 + 40 force damage. If this damage reduces the target to 0 hit points, it is disintegrated."
        },
        {
            "name": "Globe of Invulnerability",
            "school": "Abjuration",
            "casting_time": "1 action",
            "range": "Self (10-foot radius)",
            "components": "V, S, M (a glass or crystal bead that shatters when the spell ends)",
            "duration": "Concentration, up to 1 minute",
            "description": "An immobile, faintly shimmering barrier springs into existence in a 10-foot radius around you and remains for the duration. Any spell of 5th level or lower cast from outside the barrier can't affect creatures or objects within it, even if the spell is cast using a higher level spell slot."
        },
        {
            "name": "Mass Suggestion",
            "school": "Enchantment",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, M (a snake's tongue and either a bit of honeycomb or a drop of sweet oil)",
            "duration": "24 hours",
            "description": "You suggest a course of activity (limited to a sentence or two) and magically influence up to twelve creatures of your choice that you can see within range and that can hear and understand you. Creatures that can't be charmed are immune to this effect. The suggestion must be worded in such a manner as to make the course of action sound reasonable."
        },
        {
            "name": "Sunbeam",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "Self (60-foot line)",
            "components": "V, S, M (a magnifying glass)",
            "duration": "Concentration, up to 1 minute",
            "description": "A beam of brilliant light flashes out from your hand in a 5-foot-wide, 60-foot-long line. Each creature in the line must make a Constitution saving throw. On a failed save, a creature takes 6d8 radiant damage and is blinded until your next turn. On a successful save, it takes half as much damage and isn't blinded by this spell."
        },
        {
            "name": "True Seeing",
            "school": "Divination",
            "casting_time": "1 action",
            "range": "Touch",
            "components": "V, S, M (an ointment for the eyes that costs 25 gp; is made from mushroom powder, saffron, and fat; and is consumed by the spell)",
            "duration": "1 hour",
            "description": "This spell gives the willing creature you touch the ability to see things as they actually are. For the duration, the creature has truesight, notices secret doors hidden by magic, and can see into the Ethereal Plane, all out to a range of 120 feet."
        }
    ],
    "7th": [
        {
            "name": "Delayed Blast Fireball",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "150 feet",
            "components": "V, S, M (a tiny ball of bat guano and sulfur)",
            "duration": "Concentration, up to 1 minute",
            "description": "A beam of yellow light flashes from your pointing finger, then condenses to linger at a chosen point within range as a glowing bead for the duration. When the spell ends, either because your concentration is broken or because you decide to end it, the bead blossoms with a low roar into an explosion of flame that spreads around corners. Each creature in a 20-foot-radius sphere centered on that point must make a Dexterity saving throw. A creature takes 12d6 fire damage on a failed save, or half as much damage on a successful one."
        },
        {
            "name": "Etherealness",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "Self",
            "components": "V, S",
            "duration": "Up to 8 hours",
            "description": "You step into the border regions of the Ethereal Plane, in the area where it overlaps with your current plane. You remain in the Border Ethereal for the duration or until you use your action to dismiss the spell. During this time, you can move in any direction. If you move up or down, every foot of movement costs an extra foot."
        },
        {
            "name": "Finger of Death",
            "school": "Necromancy",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, S",
            "duration": "Instantaneous",
            "description": "You send negative energy coursing through a creature that you can see within range, causing it searing pain. The target must make a Constitution saving throw. It takes 7d8 + 30 necrotic damage on a failed save, or half as much damage on a successful one. A humanoid killed by this spell rises at the start of your next turn as a zombie that is permanently under your command."
        },
        {
            "name": "Forcecage",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "100 feet",
            "components": "V, S, M (ruby dust worth 1,500 gp)",
            "duration": "1 hour",
            "description": "An immobile, invisible, cube-shaped prison composed of magical force springs into existence around an area you choose within range. The prison can be a cage or a solid box, as you choose. A prison in the shape of a cage can be up to 20 feet on a side and is made from 1/2-inch diameter bars spaced 1/2 inch apart."
        },
        {
            "name": "Plane Shift",
            "school": "Conjuration",
            "casting_time": "1 action",
            "range": "Touch",
            "components": "V, S, M (a forked, metal rod worth at least 250 gp, attuned to a particular plane of existence)",
            "duration": "Instantaneous",
            "description": "You and up to eight willing creatures who link hands in a circle are transported to a different plane of existence. You can specify a target destination in general terms, such as the City of Brass on the Elemental Plane of Fire or the palace of Dispater on the second level of the Nine Hells."
        },
        {
            "name": "Prismatic Spray",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "Self (60-foot cone)",
            "components": "V, S",
            "duration": "Instantaneous",
            "description": "Eight multicolored rays of light flash from your hand. Each ray is a different color and has a different power and purpose. Each creature in a 60-foot cone must make a Dexterity saving throw. For each target, roll a d8 to determine which color ray affects it."
        },
        {
            "name": "Reverse Gravity",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "100 feet",
            "components": "V, S, M (a lodestone and iron filings)",
            "duration": "Concentration, up to 1 minute",
            "description": "This spell reverses gravity in a 50-foot-radius, 100-foot high cylinder centered on a point within range. All creatures and objects that aren't somehow anchored to the ground in the area fall upward and reach the top of the area when you cast this spell."
        },
        {
            "name": "Teleport",
            "school": "Conjuration",
            "casting_time": "1 action",
            "range": "10 feet",
            "components": "V",
            "duration": "Instantaneous",
            "description": "This spell instantly transports you and up to eight willing creatures of your choice that you can see within range, or a single object that you can see within range, to a destination you select. If you target an object, it must be able to fit entirely inside a 10-foot cube, and it can't be held or carried by an unwilling creature."
        }
    ],
    "8th": [
        {
            "name": "Antimagic Field",
            "school": "Abjuration",
            "casting_time": "1 action",
            "range": "Self (10-foot radius sphere)",
            "components": "V, S, M (a pinch of powdered iron or iron filings)",
            "duration": "Concentration, up to 1 hour",
            "description": "A 10-foot-radius invisible sphere of antimagic surrounds you. This area is divorced from the magical energy that suffuses the multiverse. Within the sphere, spells can't be cast, summoned creatures disappear, and even magic items become mundane."
        },
        {
            "name": "Clone",
            "school": "Necromancy",
            "casting_time": "1 hour",
            "range": "Touch",
            "components": "V, S, M (a diamond worth at least 1,000 gp and at least 1 cubic inch of flesh of the creature that is to be cloned, which the spell consumes, and a vessel worth at least 2,000 gp that has a sealable lid)",
            "duration": "Instantaneous",
            "description": "This spell grows an inert duplicate of a living creature as a safeguard against death. This clone forms inside the vessel and grows to full size and maturity after 120 days; you can also choose to have the clone be a younger version of the same creature."
        },
        {
            "name": "Dominate Monster",
            "school": "Enchantment",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, S",
            "duration": "Concentration, up to 1 hour",
            "description": "You attempt to beguile a creature that you can see within range. It must succeed on a Wisdom saving throw or be charmed by you for the duration. If you or creatures that are friendly to you are fighting it, it has advantage on the saving throw."
        },
        {
            "name": "Feeblemind",
            "school": "Enchantment",
            "casting_time": "1 action",
            "range": "150 feet",
            "components": "V, S, M (a handful of clay, crystal, glass, or mineral spheres)",
            "duration": "Instantaneous",
            "description": "You blast the mind of a creature that you can see within range, attempting to shatter its intellect and personality. The target takes 4d6 psychic damage and must make an Intelligence saving throw. On a failed save, the creature's Intelligence and Charisma scores become 1."
        },
        {
            "name": "Power Word Stun",
            "school": "Enchantment",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V",
            "duration": "Instantaneous",
            "description": "You speak a word of power that can overwhelm the mind of one creature you can see within range, leaving it dumbfounded. If the target has 150 hit points or fewer, it is stunned. Otherwise, the spell has no effect."
        }
    ],
    "9th": [
        {
            "name": "Gate",
            "school": "Conjuration",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V, S, M (a diamond worth at least 5,000 gp)",
            "duration": "Concentration, up to 1 minute",
            "description": "You conjure a portal linking an unoccupied space you can see within range to a precise location on a different plane of existence. The portal is a circular opening, which you can make 5 to 20 feet in diameter. You can orient the portal in any direction you choose."
        },
        {
            "name": "Meteor Swarm",
            "school": "Evocation",
            "casting_time": "1 action",
            "range": "1 mile",
            "components": "V, S",
            "duration": "Instantaneous",
            "description": "Blazing orbs of fire plummet to the ground at four different points you can see within range. Each creature in a 40-foot-radius sphere centered on each point must make a Dexterity saving throw. The sphere spreads around corners. A creature takes 20d6 fire damage and 20d6 bludgeoning damage on a failed save, or half as much damage on a successful one."
        },
        {
            "name": "Power Word Kill",
            "school": "Enchantment",
            "casting_time": "1 action",
            "range": "60 feet",
            "components": "V",
            "duration": "Instantaneous",
            "description": "You utter a word of power that can compel one creature you can see within range to die instantly. If the creature you choose has 100 hit points or fewer, it dies. Otherwise, the spell has no effect."
        },
        {
            "name": "Time Stop",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "Self",
            "components": "V",
            "duration": "Instantaneous",
            "description": "You briefly stop the flow of time for everyone but yourself. No time passes for other creatures, while you take 1d4 + 1 turns in a row, during which you can use actions and move as normal."
        },
        {
            "name": "True Polymorph",
            "school": "Transmutation",
            "casting_time": "1 action",
            "range": "30 feet",
            "components": "V, S, M (a drop of mercury, a dollop of gum arabic, and a wisp of smoke)",
            "duration": "Concentration, up to 1 hour",
            "description": "Choose one creature or nonmagical object that you can see within range. You transform the creature into a different creature, the creature into a nonmagical object, or the object into a creature. The transformation lasts for the duration, or until the target drops to 0 hit points or dies."
        },
        {
            "name": "Wish",
            "school": "Conjuration",
            "casting_time": "1 action",
            "range": "Self",
            "components": "V",
            "duration": "Instantaneous",
            "description": "The most powerful spell a mortal creature can cast. By simply speaking aloud, you can alter the very foundations of reality in accord with your desires. The basic use of this spell is to duplicate any other spell of 8th level or lower. Alternatively, you can create one of several powerful effects of your choice."
        }
    ]
}
