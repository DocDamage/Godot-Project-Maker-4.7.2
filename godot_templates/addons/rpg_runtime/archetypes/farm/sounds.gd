class_name RpgFarmSounds
extends RefCounted
## The sounds of the farm's work: the sound slots of the kind (T17.02), each played where the
## thing it names happens. A slot the game has no sound in is silent, as every slot is.
##   sfx_hoe      the hoe tilled a cell          sfx_water    the can watered one, or was filled
##   sfx_plant    a seed went into the soil      sfx_harvest  a ripe crop was picked, the sickle cut
##   sfx_animal   an animal was petted or fed    sfx_rooster  a new day began
## (`sfx_sell` is the morning's summary, RpgDayEnd; the rod and the forage play theirs themselves.)

const HOE := &"sfx_hoe"
const WATER := &"sfx_water"
const PLANT := &"sfx_plant"
const HARVEST := &"sfx_harvest"
const ANIMAL := &"sfx_animal"
const ROOSTER := &"sfx_rooster"

## The slot that was asked for last and how many were asked for, for tests: a game without an
## audio player (a unit test) plays nothing and still says what it would have played.
static var last: StringName = &""
static var count: int = 0

static func play(slot: StringName) -> void:
	if slot == &"":
		return
	last = slot
	count += 1
	RpgMenuUtil.play_ui(slot)
