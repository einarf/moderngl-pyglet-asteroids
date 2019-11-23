from pathlib import Path
import moderngl
import moderngl_window
import moderngl_window.resources
from moderngl_window import geometry
from moderngl_window import meta
from pyrr import matrix44

import pyglet, random, math
from pyglet import gl
from game import asteroid, load, player, resources


# Set up a window
window_x = 1920
window_y = 1080

config = pyglet.gl.Config(
    depth_size=24,
    double_buffer=True,
    sample_buffers=1,
    samples=8,
)

game_window = pyglet.window.Window(window_x, window_y, config=config, fullscreen=False)

main_batch = pyglet.graphics.Batch()

# Set up the two top labels
score_label = pyglet.text.Label(text="Score: 0", x=10, y=575, batch=main_batch)
level_label = pyglet.text.Label(text="Version 5: It's a Game!",
                                x=400, y=575, anchor_x='center', batch=main_batch)

# Set up the game over label offscreen
game_over_label = pyglet.text.Label(text="GAME OVER",
                                    x=400, y=-300, anchor_x='center',
                                    batch=main_batch, font_size=48)

counter = pyglet.window.FPSDisplay(window=game_window)

player_ship = None
player_lives = []
score = 0
num_asteroids = 3
game_objects = []

# We need to pop off as many event stack frames as we pushed on
# every time we reset the level.
event_stack_size = 0

ctx = moderngl.create_context()
moderngl_window.activate_context(ctx=ctx)
moderngl_window.resources.register_dir(Path(__file__).resolve().parent / 'resources')

quad = geometry.quad_2d(size=(800/600, 1.0))
fbo = ctx.framebuffer(
    color_attachments=ctx.texture((window_x, window_y), components=4),
    # depth_attachment=ctx.depth_texture((800, 600)),
)
texture_program = moderngl_window.resources.programs.load(
    meta.ProgramDescription(path='texture.glsl')
)
scene = moderngl_window.resources.scenes.load(
#    meta.SceneDescription(path='VC/glTF/VC.gltf')
    meta.SceneDescription(path='Sponza/glTF/Sponza.gltf')
)
projection = matrix44.create_perspective_projection(90, window_x/window_y, 0.1, 1000, dtype='f4')

def init():
    global score, num_asteroids

    score = 0
    score_label.text = "Score: " + str(score)

    num_asteroids = 3
    reset_level(2)


def reset_level(num_lives=2):
    global player_ship, player_lives, game_objects, event_stack_size

    # Clear the event stack of any remaining handlers from other levels
    while event_stack_size > 0:
        game_window.pop_handlers()
        event_stack_size -= 1

    for life in player_lives:
        life.delete()

    # Initialize the player sprite
    player_ship = player.Player(x=400, y=300, batch=main_batch)

    # Make three sprites to represent remaining lives
    player_lives = load.player_lives(num_lives, main_batch)

    # Make some asteroids so we have something to shoot at 
    asteroids = load.asteroids(num_asteroids, player_ship.position, main_batch)

    # Store all objects that update each frame in a list
    game_objects = [player_ship] + asteroids

    # Add any specified event handlers to the event handler stack
    for obj in game_objects:
        for handler in obj.event_handlers:
            game_window.push_handlers(handler)
            event_stack_size += 1


time = 0

@game_window.event
def on_draw():
    global time
    time += 0.01
    game_window.clear()
    ctx.screen.use()

    trans = matrix44.create_from_translation((math.cos(time), math.sin(time / 5) * 5 - 6, 0))
    rot = matrix44.create_from_y_rotation(math.pi / 2)
    mat = matrix44.multiply(trans, rot)

    ctx.enable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
    scene.draw(
        projection_matrix=projection,
        camera_matrix=mat,
    )

    fbo.use()
    fbo.clear()

    gl.glUseProgram(0)
    gl.glBindVertexArray(0)

    main_batch.draw()
    counter.draw()

    trans = matrix44.create_from_translation([0, 0, -1])
    rot = matrix44.create_from_axis_rotation([math.sin(time)/4, math.cos(time)/4, math.sin(time)/20], math.sin(time)/5)
    mat = matrix44.multiply(trans, rot)

    ctx.screen.use()
    fbo.color_attachments[0].use(location=0)
    texture_program['scale'].value = (800/window_x, 600/window_y)
    texture_program['m_proj'].write(projection)
    texture_program['m_view'].write(mat.astype('f4').tobytes())
    quad.render(texture_program)


def update(dt):
    global score, num_asteroids

    player_dead = False
    victory = False

    # To avoid handling collisions twice, we employ nested loops of ranges.
    # This method also avoids the problem of colliding an object with itself.
    for i in range(len(game_objects)):
        for j in range(i + 1, len(game_objects)):

            obj_1 = game_objects[i]
            obj_2 = game_objects[j]

            # Make sure the objects haven't already been killed
            if not obj_1.dead and not obj_2.dead:
                if obj_1.collides_with(obj_2):
                    obj_1.handle_collision_with(obj_2)
                    obj_2.handle_collision_with(obj_1)

    # Let's not modify the list while traversing it
    to_add = []

    # Check for win condition
    asteroids_remaining = 0

    for obj in game_objects:
        obj.update(dt)

        to_add.extend(obj.new_objects)
        obj.new_objects = []

        # Check for win condition
        if isinstance(obj, asteroid.Asteroid):
            asteroids_remaining += 1

    if asteroids_remaining == 0:
        # Don't act on victory until the end of the time step
        victory = True

    # Get rid of dead objects
    for to_remove in [obj for obj in game_objects if obj.dead]:
        if to_remove == player_ship:
            player_dead = True
        # If the dying object spawned any new objects, add those to the 
        # game_objects list later
        to_add.extend(to_remove.new_objects)

        # Remove the object from any batches it is a member of
        to_remove.delete()

        # Remove the object from our list
        game_objects.remove(to_remove)

        # Bump the score if the object to remove is an asteroid
        if isinstance(to_remove, asteroid.Asteroid):
            score += 1
            score_label.text = "Score: " + str(score)

    # Add new objects to the list
    game_objects.extend(to_add)

    # Check for win/lose conditions
    if player_dead:
        # We can just use the length of the player_lives list as the number of lives
        if len(player_lives) > 0:
            reset_level(len(player_lives) - 1)
        else:
            game_over_label.y = 300
    elif victory:
        num_asteroids += 1
        player_ship.delete()
        score += 10
        reset_level(len(player_lives))


if __name__ == "__main__":
    # Start it up!
    init()

    # Update the game 120 times per second
    pyglet.clock.schedule_interval(update, 1 / 60.0)

    # Tell pyglet to do its thing
    pyglet.app.run()
