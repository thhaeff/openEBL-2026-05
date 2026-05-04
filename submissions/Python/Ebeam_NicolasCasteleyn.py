import numpy as np
from siepic import all as pdk
from ipkiss3 import all as i3
from ipkiss.technology import get_technology

#%%

TECH = get_technology()

class Michelson(i3.Circuit):
    bend_radius = i3.PositiveNumberProperty(default=5.0, doc="Bend radius of the waveguides")
    fgc_spacing_y = i3.PositiveNumberProperty(default=127.0, doc="Spacing between the fiber grating couplers in the y-direction")
    fgc_dc_spacing = i3.PositiveNumberProperty(default=30.0, doc="Spacing between the fiber grating couplers in the y-direction")

    fgc = i3.ChildCellProperty(doc="PCell for the fiber grating coupler")
    splitter = i3.ChildCellProperty(doc="PCell for the Y-Branch")
    dir_coupler = i3.ChildCellProperty(doc="PCell for the directional coupler")

    delay_length = i3.PositiveNumberProperty(default=60.0, doc="length difference between the arms of the MZI")

    def _default_fgc(self):
        return pdk.EbeamGCTE1550()

    def _default_splitter(self):
        return pdk.EbeamY1550()

    def _default_dir_coupler(self):
        return pdk.EbeamBDCTE1550()
    
    def _default_specs(self):
        instances = [
            i3.Inst(["fgc_1", "fgc_2"], self.fgc),
            i3.Inst("dc", self.dir_coupler),
            i3.Inst(["yb_1", "yb_2"], self.splitter),
        ]

        fgc_spacing_y = self.fgc_spacing_y
        fgc_dc_spacing = self.fgc_dc_spacing

        placement = [
            i3.Place("fgc_1", (0, 0)),
            i3.Place("fgc_2", (0, fgc_spacing_y)),
            i3.Place("dc", (fgc_dc_spacing, fgc_spacing_y * 0.45), angle=90),
            i3.FlipV("dc"),
            i3.Place("yb_1", (fgc_dc_spacing+self.bend_radius*4.5, fgc_spacing_y* 0.15+self.bend_radius), angle=-90),
            i3.Place("yb_2", (fgc_dc_spacing+self.bend_radius*2, fgc_spacing_y* 0.15+self.bend_radius), angle=-90),
            i3.ConnectManhattan(
                [
                    ("fgc_1:opt1", "dc:opt1", "fgc_1_opt1_to_dc_opt1"),
                    ("fgc_2:opt1", "dc:opt2", "fgc_2_opt1_to_dc_opt2"),
                    
                ],
                bend_radius=self.bend_radius,  # if this value is to big the manhattan connection will not be able to fit in the layout, if it is too small the connection will be very sharp and might cause losses. You can adjust this value to find a good balance between compactness and performance.
            ),

            
            i3.ConnectManhattan(
                [
                    ("dc:opt3", "yb_2:opt1", "dc_opt3_to_yb_2_opt1",),
                    
                ],
                bend_radius=self.bend_radius,  # if this value is to big the manhattan connection will not be able to fit in the layout, if it is too small the connection will be very sharp and might cause losses. You can adjust this value to find a good balance between compactness and performance.
            # control_points=[
            #                 i3.V(fgc_spacing_y * 0.65, flexible=True)
            # ],
            ),


            # sensing arm
            i3.ConnectManhattan(
                "dc:opt4",
                "yb_1:opt1",
                "dc_opt4_to_yb_1_opt1",
            start_straight=10.0,  # add a straight section at the beginning of the connection to ensure that the waveguide is straight before it starts bending, this can help reduce losses and improve performance.
            control_points=[
                            i3.V(fgc_spacing_y * 0.5, flexible=True)
            ],
                match_path_length=i3.MatchLength(reference="dc_opt3_to_yb_2_opt1", delta=self.delay_length),
            ),

            # splitters loops
            i3.ConnectBend([
                            ("yb_1:opt2", "yb_1:opt3", "sensing_loop"), 
                            ("yb_2:opt2", "yb_2:opt3", "reference_loop"),
                ],
                bend_radius=self.bend_radius,
            ),
        ]

        specs = instances + placement
        return specs
    
    def get_connector_instances(self):
        lv_instances = self.get_default_view(i3.LayoutView).instances
        return [
            lv_instances["fgc_1_opt1_to_dc_opt1"],
            lv_instances["fgc_2_opt1_to_dc_opt2"],
            lv_instances["dc_opt4_to_yb_1_opt1"],
            lv_instances["dc_opt3_to_yb_2_opt1"],
        ]
        pass

    def _default_exposed_ports(self):
        exposed_ports = {
                            "dc:opt1": "in",
                            "dc:opt2": "out",
        }
        return exposed_ports
    
    
    def annotate_trace_template(trace):
        return {"trace template": trace.trace_template.cell.__class__.__name__}
#%%
### LAYOUT ###

# Parameters for the MZI sweep
delay_lengths = [50.0, 75.0, 100.0, 125.0, 150.0]  # Desired delay lengths in micrometers
bend_radius = 5.0
x0 = 40.0
y0 = 20.0
spacing_x = 100.0

insts = dict()
specs = []

# Create the floorplan
floorplan = pdk.FloorPlan(name="FLOORPLAN", size=(605.0, 410.0))

# Add the floorplan to the instances dict and place it at (0.0, 0.0)
specs.append(i3.Inst("floorplan", floorplan))
specs.append(i3.Place("floorplan", (0.0, 0.0)))

# Create the MZI sweep
for ind, delay_length in enumerate(delay_lengths):

    if ind == 4:
        x0 += 20.0  # Add extra spacing before the last MZI
    # Instantiate the MZI
    mzi = MZI(
        name=f"Michelson{ind}",
        delay_length=delay_length,
        bend_radius=bend_radius,
    )

    # Calculate the actual delay length and print the results
    right_arm_length = mzi.get_connector_instances()[1].reference.trace_length()
    left_arm_length = mzi.get_connector_instances()[0].reference.trace_length()
    actual_delay_length = right_arm_length - left_arm_length

    print(mzi.name, f"Desired delay length = {delay_length} um", f"Actual delay length = {actual_delay_length} um")

    # Add the MZI to the instances dict and place it
    mzi_cell_name = f"michelson{ind}"
    specs.append(i3.Inst(mzi_cell_name, mzi))
    specs.append(i3.Place(mzi_cell_name, (x0, y0)))

    x0 += spacing_x

# Create the final design with i3.Circuit
cell = i3.Circuit(
    name="EBeam_NicolasCasteleyn_v2",
    specs=specs,
)

# Layout
cell_lv = cell.Layout()
cell_lv.visualize(annotate=True)
cell_lv.write_gdsii("EBeam_NicolasCasteleyn_v2.gds")

# Circuit model
cell_cm = cell.CircuitModel()
wavelengths = np.linspace(1.52, 1.58, 4001)
S_total = cell_cm.get_smatrix(wavelengths=wavelengths)

if __name__ == "__main__":
    # Plotting
    for ind, delay_length in enumerate(delay_lengths):
        S_total.visualize(
            term_pairs=[(f"mzi{ind}_in:0", f"mzi{ind}_out1:0"), (f"mzi{ind}_in:0", f"mzi{ind}_out2:0")],
            title=f"MZI{ind} - Delay length {delay_length} um",
            scale="dB",
        )

    print("Done")